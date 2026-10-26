import { Construct } from 'constructs';
import { Duration } from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3n from 'aws-cdk-lib/aws-s3-notifications';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import * as tasks from 'aws-cdk-lib/aws-stepfunctions-tasks';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import { backendCode, NODE_RUNTIME } from '../backend-code';
import { APP_PREFIX, RAW_PREFIX, PROFILES_PREFIX } from '../config';

export interface PipelineProps {
  readonly mediaBucket: s3.Bucket;
  readonly videosTable: dynamodb.Table;
  readonly settingsTable: dynamodb.Table;
}

/**
 * Pipeline de processamento: S3 (raw) -> Step Functions (MediaConvert ||
 * Transcribe) -> finalize (DynamoDB status=revisar + custo). Erros -> status=erro.
 */
export class PipelineConstruct extends Construct {
  public readonly stateMachine: sfn.StateMachine;
  public readonly finalizeFn: lambda.Function;

  constructor(scope: Construct, id: string, props: PipelineProps) {
    super(scope, id);

    const { mediaBucket, videosTable, settingsTable } = props;
    const code = backendCode();

    // ---- Roles de serviço ----
    const mediaConvertRole = new iam.Role(this, 'MediaConvertRole', {
      assumedBy: new iam.ServicePrincipal('mediaconvert.amazonaws.com'),
      description: 'Role usada pelos jobs do MediaConvert para ler/gravar no S3',
    });
    mediaBucket.grantReadWrite(mediaConvertRole);

    // Observação: para bucket na MESMA conta, o Amazon Transcribe acessa o S3
    // pelo acesso de serviço — NÃO passamos DataAccessRole (passar dispara uma
    // validação que falha com "bucket can't be accessed"). Validado em deploy real.

    // ---- Env comum ----
    const commonEnv: Record<string, string> = {
      VIDEOS_TABLE: videosTable.tableName,
      MEDIA_BUCKET: mediaBucket.bucketName,
      SETTINGS_TABLE: settingsTable.tableName,
      RAW_PREFIX,
      PROFILES_PREFIX,
      APP_PREFIX,
    };

    const mkFn = (name: string, handler: string, extraEnv: Record<string, string> = {}, timeout = Duration.minutes(1)) =>
      new lambda.Function(this, name, {
        runtime: NODE_RUNTIME,
        code,
        handler,
        timeout,
        memorySize: 256,
        environment: { ...commonEnv, ...extraEnv },
      });

    // ---- Lambdas de task ----
    const startMediaConvertFn = mkFn('StartMediaConvertFn', 'pipeline/start-mediaconvert.handler', {
      MEDIACONVERT_ROLE_ARN: mediaConvertRole.roleArn,
    });
    settingsTable.grantReadData(startMediaConvertFn);
    startMediaConvertFn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['mediaconvert:CreateJob', 'mediaconvert:DescribeEndpoints', 'mediaconvert:GetJob'],
        resources: ['*'],
      })
    );
    startMediaConvertFn.addToRolePolicy(
      new iam.PolicyStatement({ actions: ['iam:PassRole'], resources: [mediaConvertRole.roleArn] })
    );
    videosTable.grantReadWriteData(startMediaConvertFn);

    const startTranscribeFn = mkFn('StartTranscribeFn', 'pipeline/start-transcribe.handler');
    startTranscribeFn.addToRolePolicy(
      new iam.PolicyStatement({ actions: ['transcribe:StartTranscriptionJob'], resources: ['*'] })
    );
    // Sem DataAccessRole, o Transcribe valida o acesso ao S3 usando as permissões
    // de QUEM chamou (esta Lambda); por isso ela precisa de leitura/escrita no bucket.
    mediaBucket.grantReadWrite(startTranscribeFn);
    videosTable.grantReadWriteData(startTranscribeFn);
    settingsTable.grantReadData(startTranscribeFn);

    const mediaConvertCallbackFn = mkFn('MediaConvertCallbackFn', 'pipeline/mediaconvert-callback.handler');
    const transcribeCallbackFn = mkFn('TranscribeCallbackFn', 'pipeline/transcribe-callback.handler');
    const finalizeFn = mkFn('FinalizeFn', 'pipeline/finalize.handler');
    this.finalizeFn = finalizeFn;
    settingsTable.grantReadData(finalizeFn);
    const onErrorFn = mkFn('OnErrorFn', 'pipeline/on-error.handler');

    // Permissões dos callbacks: retomar a Step Functions + ler/escrever recursos.
    const sendTaskPolicy = new iam.PolicyStatement({
      actions: ['states:SendTaskSuccess', 'states:SendTaskFailure', 'states:SendTaskHeartbeat'],
      resources: ['*'],
    });
    mediaConvertCallbackFn.addToRolePolicy(sendTaskPolicy);
    videosTable.grantReadData(mediaConvertCallbackFn);

    transcribeCallbackFn.addToRolePolicy(sendTaskPolicy);
    transcribeCallbackFn.addToRolePolicy(
      new iam.PolicyStatement({ actions: ['transcribe:GetTranscriptionJob'], resources: ['*'] })
    );
    mediaBucket.grantReadWrite(transcribeCallbackFn);
    videosTable.grantReadData(transcribeCallbackFn);

    videosTable.grantReadWriteData(finalizeFn); // lê pipelineStartedAt (tempo) + escreve status
    videosTable.grantWriteData(onErrorFn);

    // ---- Definição da Step Functions ----
    const mcTask = new tasks.LambdaInvoke(this, 'StartMediaConvert', {
      lambdaFunction: startMediaConvertFn,
      integrationPattern: sfn.IntegrationPattern.WAIT_FOR_TASK_TOKEN,
      payload: sfn.TaskInput.fromObject({
        videoId: sfn.JsonPath.stringAt('$.videoId'),
        sourceKey: sfn.JsonPath.stringAt('$.sourceKey'),
        taskToken: sfn.JsonPath.taskToken,
      }),
      taskTimeout: sfn.Timeout.duration(Duration.hours(6)),
    });

    const trTask = new tasks.LambdaInvoke(this, 'StartTranscribe', {
      lambdaFunction: startTranscribeFn,
      integrationPattern: sfn.IntegrationPattern.WAIT_FOR_TASK_TOKEN,
      payload: sfn.TaskInput.fromObject({
        videoId: sfn.JsonPath.stringAt('$.videoId'),
        sourceKey: sfn.JsonPath.stringAt('$.sourceKey'),
        taskToken: sfn.JsonPath.taskToken,
      }),
      taskTimeout: sfn.Timeout.duration(Duration.hours(6)),
    });

    const processVideo = new sfn.Parallel(this, 'ProcessVideo', { resultPath: '$.results' })
      .branch(mcTask)
      .branch(trTask);

    const finalizeTask = new tasks.LambdaInvoke(this, 'Finalize', {
      lambdaFunction: finalizeFn,
      payload: sfn.TaskInput.fromObject({
        videoId: sfn.JsonPath.stringAt('$.videoId'),
        results: sfn.JsonPath.objectAt('$.results'),
      }),
      payloadResponseOnly: true,
    });

    const onErrorTask = new tasks.LambdaInvoke(this, 'OnError', {
      lambdaFunction: onErrorFn,
      payload: sfn.TaskInput.fromObject({
        videoId: sfn.JsonPath.stringAt('$.videoId'),
        error: sfn.JsonPath.objectAt('$.error'),
      }),
      payloadResponseOnly: true,
    });

    processVideo.addCatch(onErrorTask, { resultPath: '$.error' });
    // Catch também no finalize: se ele falhar, marca "erro" (não deixa travado).
    finalizeTask.addCatch(onErrorTask, { resultPath: '$.error' });

    this.stateMachine = new sfn.StateMachine(this, 'Pipeline', {
      stateMachineName: `${APP_PREFIX}-pipeline`,
      definitionBody: sfn.DefinitionBody.fromChainable(processVideo.next(finalizeTask)),
      stateMachineType: sfn.StateMachineType.STANDARD,
      timeout: Duration.hours(12),
    });

    // ---- Gatilho S3 -> startExecution ----
    const startExecutionFn = mkFn('StartExecutionFn', 'pipeline/start-execution.handler', {
      STATE_MACHINE_ARN: this.stateMachine.stateMachineArn,
    });
    this.stateMachine.grantStartExecution(startExecutionFn);
    videosTable.grantWriteData(startExecutionFn);

    mediaBucket.addEventNotification(
      s3.EventType.OBJECT_CREATED,
      new s3n.LambdaDestination(startExecutionFn),
      { prefix: `${RAW_PREFIX}/` }
    );

    // ---- Regras EventBridge (conclusão dos jobs) ----
    new events.Rule(this, 'MediaConvertDoneRule', {
      ruleName: `${APP_PREFIX}-mediaconvert-done`,
      eventPattern: {
        source: ['aws.mediaconvert'],
        detailType: ['MediaConvert Job State Change'],
        detail: { status: ['COMPLETE', 'ERROR', 'CANCELED'] },
      },
      targets: [new targets.LambdaFunction(mediaConvertCallbackFn)],
    });

    new events.Rule(this, 'TranscribeDoneRule', {
      ruleName: `${APP_PREFIX}-transcribe-done`,
      eventPattern: {
        source: ['aws.transcribe'],
        detailType: ['Transcribe Job State Change'],
        detail: { TranscriptionJobStatus: ['COMPLETED', 'FAILED'] },
      },
      targets: [new targets.LambdaFunction(transcribeCallbackFn)],
    });
  }
}
