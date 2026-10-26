"""
Lib compartilhada de campanhas WhatsApp (usada pelo HTML tester, pelo loader e pelo setup).
Modelo: 1 template -> 1 pasta S3 + 1 object type + 1 event trigger (+ 1 campanha na aprovacao).

Nomes derivados do nome do template:
  object type : Campaign-<slug>
  event trigger: trigger-<slug>
  pasta S3    : campanhas/<slug>/
"""
import json
import os
import re

REGION = os.environ.get('AWS_REGION', 'us-east-1')
ACCOUNT = os.environ.get('AWS_ACCOUNT_ID', '123456789012')
WABA_ID = os.environ.get('WABA_ID', 'waba-b7e8aaaa528c4a73a9dc4212f4323c79')
INSTANCE_ID = '82a1c25d-b923-4bd2-9c21-e7eba7f052ac'
KB_ID = '5ad83ec7-1668-4dd6-92d1-7ab9d5e807c5'
KB_ARN = f'arn:aws:wisdom:{REGION}:{ACCOUNT}:knowledge-base/{KB_ID}'
CP_DOMAIN = 'amazon-connect-connect-demo-ps'
CP_DOMAIN_ARN = f'arn:aws:profile:{REGION}:{ACCOUNT}:domains/{CP_DOMAIN}'
WPP_NUMBER_ARN = f'arn:aws:connect:{REGION}:{ACCOUNT}:phone-number/15646f7c-964b-40a5-9097-6432f82945f8'


def slug(name):
    return re.sub(r'[^A-Za-z0-9_-]', '-', (name or '').strip())


def object_type_name(template_name):
    return f'Campaign-{slug(template_name)}'


def trigger_name(template_name):
    return f'trigger-{slug(template_name)}'


def s3_folder(template_name):
    return f'campanhas/{slug(template_name)}/'


def _load_template(sm, waba_id, meta_template_id):
    d = sm.get_whatsapp_message_template(id=waba_id, metaTemplateId=meta_template_id)
    tpl = d.get('template')
    if isinstance(tpl, (bytes, bytearray)):
        tpl = tpl.decode('utf-8')
    if isinstance(tpl, str):
        tpl = json.loads(tpl)
    return tpl


def template_columns(sm, waba_id, meta_template_id):
    """Retorna (name, language, columns, legend).
    columns = ['phone','var1',...] (1 coluna por variavel, header antes de body).
    legend  = [{column, placeholder, component, example}]."""
    tpl = _load_template(sm, waba_id, meta_template_id)
    cols, legend, n = ['phone'], [], 0
    for c in tpl.get('components', []):
        ctype = c.get('type')
        if ctype not in ('HEADER', 'BODY') or not c.get('text'):
            continue
        if ctype == 'HEADER' and c.get('format', 'TEXT') != 'TEXT':
            continue
        idxs = sorted({int(x) for x in re.findall(r'\{\{(\d+)\}\}', c['text'])})
        if ctype == 'HEADER':
            exs = (c.get('example', {}) or {}).get('header_text', [])
        else:
            ew = (c.get('example', {}) or {}).get('body_text', [[]])
            exs = ew[0] if ew else []
        for i, idx in enumerate(idxs):
            n += 1
            cols.append(f'var{n}')
            legend.append({'column': f'var{n}', 'component': ctype.lower(),
                           'placeholder': '{{%d}}' % idx,
                           'example': exs[i] if i < len(exs) else ''})
    return tpl.get('name'), tpl.get('language'), cols, legend


def ensure_object_type(cp, template_name, columns, domain=CP_DOMAIN):
    """Cria/atualiza o object type do template: phone (chave) + varN -> Attributes.varN."""
    fields = {'phone': {'Source': '_source.phone', 'Target': '_profile.PhoneNumber',
                        'ContentType': 'PHONE_NUMBER'}}
    for col in columns:
        if col == 'phone':
            continue
        fields[col] = {'Source': f'_source.{col}', 'Target': f'_profile.Attributes.{col}'}
    otn = object_type_name(template_name)
    cp.put_profile_object_type(
        DomainName=domain, ObjectTypeName=otn,
        Description=f'Campanha WhatsApp "{template_name}" - disparo fiel ao CSV',
        AllowProfileCreation=True, Fields=fields,
        Keys={'_phone': [{'StandardIdentifiers': ['PROFILE', 'UNIQUE'], 'FieldNames': ['phone']}]})
    return otn


def ensure_event_trigger(cp, template_name, domain=CP_DOMAIN):
    """Cria o event trigger do template (idempotente). Condicao: telefone comeca com '+'
    (casa todo objeto ingerido daquele object type = daquela pasta/template)."""
    otn = object_type_name(template_name)
    tname = trigger_name(template_name)
    try:
        cp.create_event_trigger(
            DomainName=domain, EventTriggerName=tname, ObjectTypeName=otn,
            Description=f'Dispara campanha "{template_name}" por objeto ingerido (fiel ao CSV)',
            EventTriggerConditions=[{
                'EventTriggerDimensions': [{'ObjectAttributes': [
                    {'Source': 'phone', 'ComparisonOperator': 'BEGINS_WITH', 'Values': ['+']}]}],
                'LogicalOperator': 'ANY'}],
            EventTriggerLimits={'EventExpiration': 900000,
                                'Periods': [{'Unit': 'DAYS', 'Value': 1,
                                             'MaxInvocationsPerProfile': 1000}]})
    except cp.exceptions.BadRequestException as e:
        if 'already exists' not in str(e).lower():
            raise
    return tname


def ensure_s3_folder(s3, bucket, template_name):
    """Cria um marcador de pasta no S3 (S3 nao tem pastas de verdade; e um prefixo)."""
    key = s3_folder(template_name) + '.keep'
    s3.put_object(Bucket=bucket, Key=key, Body=b'')
    return s3_folder(template_name)


# ---- message template + campanha (dependem do template Meta APROVADO) ----

def approved_template(sm, template_name, waba_id=WABA_ID):
    """Retorna o dict do template na WABA (ou None). templateStatus indica se esta APPROVED."""
    for t in sm.list_whatsapp_message_templates(id=waba_id).get('templates', []):
        if t.get('templateName') == template_name:
            return t
    return None


def message_template_name(template_name):
    return f'camp_{slug(template_name)}'


def campaign_name(template_name):
    return f'campanha-{slug(template_name)}'


def find_message_template(q, template_name, kb_id=KB_ID):
    want = message_template_name(template_name)
    token = None
    while True:
        kw = {'knowledgeBaseId': kb_id, 'maxResults': 100}
        if token:
            kw['nextToken'] = token
        r = q.list_message_templates(**kw)
        for t in r.get('messageTemplateSummaries', []):
            if t.get('name') == want:
                return t.get('messageTemplateArn')
        token = r.get('nextToken')
        if not token:
            return None


def source_components(sm, meta_template_id, waba_id=WABA_ID):
    """Mapeia os parametros posicionais do template ({{1}},{{2}}...) para atributos custom de
    perfil ({{Attributes.Customer.Attributes.varN}} - sintaxe validada via RenderMessageTemplate),
    na MESMA ordem/numeracao de template_columns (header antes de body). Formato exigido por
    sourceConfiguration.whatsApp.components (lista de JSON strings)."""
    tpl = _load_template(sm, waba_id, meta_template_id)
    comps, n = [], 0
    for c in tpl.get('components', []):
        ctype = c.get('type')
        if ctype not in ('HEADER', 'BODY') or not c.get('text'):
            continue
        if ctype == 'HEADER' and c.get('format', 'TEXT') != 'TEXT':
            continue
        idxs = sorted({int(x) for x in re.findall(r'\{\{(\d+)\}\}', c['text'])})
        if not idxs:
            continue
        params = []
        for _ in idxs:
            n += 1
            # sintaxe correta p/ atributo custom de perfil em campanha (validado via render):
            # {{Attributes.Customer.Attributes.<nome>}}
            params.append({'type': 'text', 'text': f'{{{{Attributes.Customer.Attributes.var{n}}}}}'})
        comps.append(json.dumps({'type': ctype, 'parameters': params}))
    return comps


def ensure_message_template(q, sm, template_name, meta_template_id, language, kb_id=KB_ID,
                            waba_id=WABA_ID):
    """WHATSAPP: usa sourceConfiguration (exige template Meta APROVADO). Idempotente.
    Quando o template tem variaveis, inclui o mapeamento components ({{N}} -> atributo)."""
    arn = find_message_template(q, template_name, kb_id)
    if arn:
        return arn
    src = {'businessAccountId': waba_id, 'templateId': meta_template_id}
    comps = source_components(sm, meta_template_id, waba_id)
    if comps:
        src['components'] = comps
    r = q.create_message_template(
        knowledgeBaseId=kb_id, name=message_template_name(template_name),
        channelSubtype='WHATSAPP', language=language or 'pt_BR',
        sourceConfiguration={'whatsApp': src},
        # OBRIGATORIO: sem esta tag a service role do connect-campaigns e NEGADA em
        # wisdom:RenderMessageTemplate e a campanha completa sem enviar (falha silenciosa).
        tags={'AmazonConnectCampaignsEnabled': 'True'})
    arn = r['messageTemplate'].get('messageTemplateArn')
    # o KB tambem precisa da tag (a condicao wisdom da SLR aplica a qualquer recurso wisdom)
    try:
        q.tag_resource(resourceArn=KB_ARN, tags={'AmazonConnectCampaignsEnabled': 'True'})
    except Exception:
        pass
    return arn


def ensure_campaign_flow(connect, template_name, wisdom_arn, instance_id=INSTANCE_ID,
                         phone_arn=WPP_NUMBER_ARN, kb_arn=KB_ARN):
    """Cria/atualiza o CAMPAIGN flow do template (SendWhatsAppMessage -> template ATUAL) e
    publica uma versao. CRITICO: o flow e quem envia no modo agentless; ele NAO pode apontar
    para um template antigo/deletado, senao o envio falha silenciosamente."""
    name = f'campanha-{slug(template_name)}-flow'
    content = json.dumps({
        'Version': '2019-10-30', 'StartAction': 'send',
        'Actions': [
            {'Identifier': 'send', 'Type': 'SendWhatsAppMessage', 'Parameters': {
                'Message': {'MessageSourceType': 'TEMPLATE', 'TemplatedMessage': {
                    'WisdomKnowledgeBaseArn': kb_arn, 'WisdomMessageTemplateArn': wisdom_arn}},
                'SourceEndpoint': {'Address': phone_arn, 'Type': 'CONNECT_PHONENUMBER_ARN'}},
             'Transitions': {'NextAction': 'end', 'Conditions': [],
                             'Errors': [{'NextAction': 'end', 'ErrorType': 'NoMatchingError'}]}},
            {'Identifier': 'end', 'Type': 'EndFlowExecution', 'Parameters': {}}]})
    try:
        fid = connect.create_contact_flow(InstanceId=instance_id, Name=name, Type='CAMPAIGN',
                                          Content=content)['ContactFlowId']
    except connect.exceptions.DuplicateResourceException:
        fid = next(f['Id'] for f in connect.list_contact_flows(InstanceId=instance_id)['ContactFlowSummaryList']
                   if f['Name'] == name)
        connect.update_contact_flow_content(InstanceId=instance_id, ContactFlowId=fid, Content=content)
    v = connect.create_contact_flow_version(InstanceId=instance_id, ContactFlowId=fid)
    return f"{v['ContactFlowArn']}:{v['Version']}"


def create_phone_segment(cp, seg_name, phones, domain=CP_DOMAIN):
    """Cria um segmento DEDICADO (nome unico por disparo) por lista de telefones, fiel ao CSV:
    PhoneNumber INCLUSIVE [phones]. PhoneNumber e atributo padrao -> materializa confiavel."""
    groups = {'Groups': [{'Dimensions': [{'ProfileAttributes': {
        'PhoneNumber': {'DimensionType': 'INCLUSIVE', 'Values': phones}}}], 'Type': 'ANY'}],
        'Include': 'ANY'}
    try:
        r = cp.create_segment_definition(DomainName=domain, SegmentDefinitionName=seg_name,
                                         DisplayName=seg_name[:60], SegmentGroups=groups)
        return r['SegmentDefinitionArn']
    except cp.exceptions.BadRequestException as e:
        if 'already exists' in str(e).lower():
            cp.delete_segment_definition(DomainName=domain, SegmentDefinitionName=seg_name)
            r = cp.create_segment_definition(DomainName=domain, SegmentDefinitionName=seg_name,
                                             DisplayName=seg_name[:60], SegmentGroups=groups)
            return r['SegmentDefinitionArn']
        raise


def find_campaign(cc, template_name, instance_id=INSTANCE_ID):
    want = campaign_name(template_name)
    token = None
    while True:
        kw = {'filters': {'instanceIdFilter': {'value': instance_id, 'operator': 'Eq'}}}
        if token:
            kw['nextToken'] = token
        r = cc.list_campaigns(**kw)
        for c in r.get('campaignSummaryList', []):
            if c.get('name') == want:
                return c.get('id')
        token = r.get('nextToken')
        if not token:
            return None


def create_dispatch_campaign(cc, campaign_name_str, wisdom_arn, flow_arn, segment_arn,
                             instance_id=INSTANCE_ID, phone_arn=WPP_NUMBER_ARN,
                             timezone='America/Sao_Paulo'):
    """Cria uma campanha NOVA (nome unico por disparo) com a receita comprovada:
    source=segmento dedicado, connectCampaignFlowArn=flow (envia com o template atual),
    schedule (start +6min, min da API), open hours 24/7, tag owner, start."""
    import datetime
    dias = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY']
    oh = {d: [{'startTime': 'T00:00', 'endTime': 'T23:59'}] for d in dias}
    now = datetime.datetime.now(datetime.timezone.utc)
    start = now + datetime.timedelta(minutes=6)
    end = now + datetime.timedelta(days=365)
    r = cc.create_campaign(
        name=campaign_name_str, connectInstanceId=instance_id, type='MANAGED',
        connectCampaignFlowArn=flow_arn,
        channelSubtypeConfig={'whatsApp': {'capacity': 1.0, 'outboundMode': {'agentless': {}},
            'defaultOutboundConfig': {'connectSourcePhoneNumberArn': phone_arn,
                                      'wisdomTemplateArn': wisdom_arn}}},
        source={'customerProfilesSegmentArn': segment_arn},
        schedule={'startTime': start, 'endTime': end},
        communicationTimeConfig={'localTimeZoneConfig': {'defaultTimeZone': timezone},
            'whatsApp': {'openHours': {'dailyHours': oh}}})
    cid = r['id']
    cc.tag_resource(arn=f'arn:aws:connect-campaigns:{REGION}:{ACCOUNT}:campaign/{cid}',
                    tags={'owner': f'arn:aws:connect:{REGION}:{ACCOUNT}:instance/{instance_id}'})
    cc.start_campaign(id=cid)
    return cid


def dedupe_profiles_by_phone(cp, phones, domain=CP_DOMAIN):
    """Para cada telefone, se houver >1 perfil, mescla todos em UM (evita envio duplicado na
    campanha, ja que o segmento casa por PhoneNumber). O AutoMerging do dominio faz isso, mas
    e batch/periodico; aqui garantimos 1 perfil por telefone JA no disparo. Mantem como
    principal o perfil com mais atributos preenchidos."""
    merged = 0
    for phone in {p for p in phones if p}:
        items = cp.search_profiles(DomainName=domain, KeyName='_phone', Values=[phone]).get('Items', [])
        if len(items) < 2:
            continue

        def score(p):
            a = p.get('Attributes') or {}
            std = sum(1 for k in ('FirstName', 'LastName', 'AccountNumber', 'EmailAddress') if p.get(k))
            return std + sum(1 for v in a.values() if v)

        items.sort(key=score, reverse=True)
        main = items[0]['ProfileId']
        others = [p['ProfileId'] for p in items[1:]]
        try:
            cp.merge_profiles(DomainName=domain, MainProfileId=main, ProfileIdsToBeMerged=others)
            merged += len(others)
        except Exception:
            pass
    return merged


def dispatch_campaign(sm, q, cc, connect, cp, template_name, meta_template_id, phones,
                      label=None, language=None):
    """UM disparo = UMA campanha NOVA + UM segmento dedicado (sem duplicidade).
    Nome da campanha = <label>-<AAAAMMDD-HHMMSS> (rotulo do HTML + data/hora, evita colisao).
    Passos: dedup perfis por telefone -> message template (binding+tags) -> campaign flow
    (template atual) -> segmento dedicado (fiel ao CSV) -> campanha NOVA (start)."""
    import datetime
    t = approved_template(sm, template_name)
    status = (t or {}).get('templateStatus')
    if status != 'APPROVED':
        return {'campaignId': None, 'created': False, 'pending': True,
                'status': status or 'NOT_FOUND'}
    lang = language or (t or {}).get('templateLanguage', 'pt_BR')
    dedupe_profiles_by_phone(cp, phones)
    wisdom_arn = ensure_message_template(q, sm, template_name, meta_template_id, lang)
    flow_arn = ensure_campaign_flow(connect, template_name, wisdom_arn)
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    base = slug(label) if label else slug(template_name)
    disp = f'{base}-{stamp}'[:120]
    seg_arn = create_phone_segment(cp, f'seg-{disp}'[:64].rstrip('-'), phones)
    cid = create_dispatch_campaign(cc, disp, wisdom_arn, flow_arn, seg_arn)
    return {'campaignId': cid, 'campaignName': disp, 'created': True, 'pending': False,
            'status': 'APPROVED', 'wisdomArn': wisdom_arn, 'flowArn': flow_arn,
            'segmentArn': seg_arn, 'destinatarios': len({p for p in phones if p})}
