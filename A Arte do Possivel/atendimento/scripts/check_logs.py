"""Check logs from Connect and Lambdas."""
import boto3
import json
import time

REGION = 'us-east-1'
logs = boto3.client('logs', region_name=REGION)
end_time = int(time.time() * 1000)
start_time = end_time - (5 * 60 * 1000)

log_groups = [
    '/aws/connect/connect-demo-ps',
    '/aws/lambda/mcp-catalogo-cursos',
    '/aws/lambda/connect-user-lookup',
    '/aws/lambda/mcp-academico',
    '/aws/lambda/connect-harness-integration',
    '/aws/lambda/connect-harness-async',
    '/aws/lambda/lex-harness-fulfillment',
]

for group in log_groups:
    try:
        resp = logs.filter_log_events(
            logGroupName=group,
            startTime=start_time,
            endTime=end_time,
            limit=10
        )
        events = resp.get('events', [])
        if events:
            print(f'\n=== {group} ({len(events)} events) ===')
            for e in events:
                msg = e['message'].strip()
                if msg and 'START' not in msg and 'END' not in msg and 'REPORT' not in msg and 'INIT' not in msg:
                    print(f'  {msg[:300]}')
        else:
            print(f'{group}: no events')
    except Exception as e:
        print(f'{group}: {str(e)[:80]}')
