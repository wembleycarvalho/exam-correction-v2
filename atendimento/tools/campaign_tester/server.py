"""
Tester visual local de templates WhatsApp (AWS End User Messaging Social).
Servidor stdlib (sem dependencias). Ao selecionar um template, le a definicao real na
AWS, mostra o preview do corpo e monta um campo por variavel ({{1}}, {{2}}...).

Rodar (carrega o .env sozinho):
  python3 tools/campaign_tester/server.py      ->  http://127.0.0.1:8899
"""
import json
import os
import re
import http.server
import socketserver


def _load_dotenv():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    path = os.path.join(root, '.env')
    if not os.path.exists(path):
        return
    for line in open(path):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[len('export '):]
        if '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'scripts'))
import boto3
import campaign_lib as lib

REGION = os.environ.get('AWS_REGION', 'us-east-1')
WABA_ID = os.environ.get('WABA_ID', 'waba-b7e8aaaa528c4a73a9dc4212f4323c79')
ORIGIN = os.environ.get('WHATSAPP_PHONE_NUMBER_ID', 'phone-number-id-fe268d418d9b4e1296c47f86795987df')
META_API = os.environ.get('META_API_VERSION', 'v20.0')
PORT = int(os.environ.get('TESTER_PORT', '8899'))

sm = boto3.client('socialmessaging', region_name=REGION)
cp = boto3.client('customer-profiles', region_name=REGION)
s3 = boto3.client('s3', region_name=REGION)
q = boto3.client('qconnect', region_name=REGION)
cc = boto3.client('connectcampaignsv2', region_name=REGION)
connect = boto3.client('connect', region_name=REGION)
CP_DOMAIN = os.environ.get('CP_DOMAIN', 'amazon-connect-connect-demo-ps')
CAMPAIGN_OBJECT_TYPE = os.environ.get('CAMPAIGN_OBJECT_TYPE', 'Campaign-WhatsApp')
CAMPAIGN_BUCKET = os.environ.get('CAMPAIGN_BUCKET', '')


def _components(meta_template_id):
    d = sm.get_whatsapp_message_template(id=WABA_ID, metaTemplateId=meta_template_id)
    tpl = d.get('template')
    if isinstance(tpl, (bytes, bytearray)):
        tpl = tpl.decode('utf-8')
    if isinstance(tpl, str):
        tpl = json.loads(tpl)
    return tpl.get('components', []), tpl


def _indices(text):
    return sorted({int(n) for n in re.findall(r'\{\{(\d+)\}\}', text or '')})


def template_detail(meta_template_id):
    comps, tpl = _components(meta_template_id)
    out = {'name': tpl.get('name'), 'language': tpl.get('language'), 'parts': []}
    for c in comps:
        ctype = c.get('type')
        if ctype == 'HEADER' and c.get('format', 'TEXT') == 'TEXT' and c.get('text'):
            idx = _indices(c['text'])
            if idx:
                ex = (c.get('example', {}) or {}).get('header_text', [])
                out['parts'].append({'component': 'header', 'text': c['text'],
                                     'indices': idx, 'examples': ex})
        elif ctype == 'BODY':
            idx = _indices(c.get('text', ''))
            ex_wrap = (c.get('example', {}) or {}).get('body_text', [[]])
            ex = ex_wrap[0] if ex_wrap else []
            out['parts'].append({'component': 'body', 'text': c.get('text', ''),
                                 'indices': idx, 'examples': ex})
        elif ctype == 'FOOTER':
            out['parts'].append({'component': 'footer', 'text': c.get('text', ''),
                                 'indices': [], 'examples': []})
        elif ctype == 'BUTTONS':
            out['parts'].append({'component': 'buttons', 'text': '',
                                 'buttons': [b.get('text', '') for b in c.get('buttons', [])],
                                 'indices': [], 'examples': []})
        else:
            out['parts'].append({'component': (ctype or 'other').lower(),
                                 'text': c.get('text', ''), 'indices': [], 'examples': []})
    return out


def campaign_columns(meta_template_id=None):
    """Campos esperados do CSV do template selecionado + nomes dos recursos daquele template
    (object type e pasta S3 proprios)."""
    base = {'bucket': CAMPAIGN_BUCKET, 'phone': 'phone'}
    if not meta_template_id:
        base.update({'columns': ['phone'], 'legend': []})
        return base
    name, lang, cols, legend = lib.template_columns(sm, WABA_ID, meta_template_id)
    base.update({'name': name, 'language': lang, 'columns': cols, 'legend': legend,
                 'objectType': lib.object_type_name(name), 'folder': lib.s3_folder(name)})
    return base


def campaign_send(csv_text, filename, meta_template_id, campaign_label=None):
    """Grava 1 perfil por linha do CSV, sobe o CSV no S3 e cria UMA campanha nova (nome =
    campaign_label + data/hora) com segmento dedicado, fiel ao CSV."""
    import csv as _csv
    import io
    import datetime
    if not CAMPAIGN_BUCKET:
        return {'error': 'CAMPAIGN_BUCKET nao definido no .env (rode scripts/setup_campaign_native.py)'}
    if not meta_template_id:
        return {'error': 'selecione o template da campanha'}
    name, lang, cols, legend = lib.template_columns(sm, WABA_ID, meta_template_id)
    lib.ensure_object_type(cp, name, cols)
    lib.ensure_s3_folder(s3, CAMPAIGN_BUCKET, name)
    otn = lib.object_type_name(name)
    folder = lib.s3_folder(name)
    stamp = datetime.datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    safe = re.sub(r'[^A-Za-z0-9._-]', '_', filename or 'campanha.csv')
    key = f'{folder}{stamp}-{safe}'
    s3.put_object(Bucket=CAMPAIGN_BUCKET, Key=key, Body=csv_text.encode('utf-8'),
                  ContentType='text/csv')
    # 1) grava 1 perfil por linha + coleta a lista de telefones (fiel ao CSV)
    rows = list(_csv.DictReader(io.StringIO(csv_text)))
    ok, errs, phones = 0, [], []
    for i, row in enumerate(rows, 1):
        phone = (row.get('phone') or row.get('Phone') or '').strip()
        if not phone:
            errs.append(f'linha {i}: sem phone')
            continue
        if not phone.startswith('+'):
            phone = '+' + phone
        obj = {'phone': phone}
        for k, v in row.items():
            if k and k.strip().lower() != 'phone' and v and v.strip():
                obj[k.strip()] = v.strip()
        try:
            cp.put_profile_object(DomainName=CP_DOMAIN, ObjectTypeName=otn, Object=json.dumps(obj))
            ok += 1
            if phone not in phones:
                phones.append(phone)
        except Exception as e:
            errs.append(f'linha {i}: {e}')
    # 2) UM disparo = UMA campanha NOVA (nome = label + data/hora) + segmento dedicado, fiel ao CSV
    try:
        if phones:
            camp = lib.dispatch_campaign(sm, q, cc, connect, cp, name, meta_template_id, phones,
                                         label=(campaign_label or name), language=lang)
        else:
            camp = {'pending': True, 'status': 'SEM_TELEFONES'}
    except Exception as e:
        camp = {'error': str(e)}
    return {'ok': True, 'template': name, 'objectType': otn, 'campaign': camp,
            's3': f's3://{CAMPAIGN_BUCKET}/{key}', 'gravados': ok, 'destinatarios': len(phones),
            'total': len(rows), 'erros': errs}


PAGE = r"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<title>WhatsApp Template Tester</title>
<style>
 body{font-family:system-ui,Segoe UI,Arial;margin:0;background:#0b141a;color:#e9edef}
 .wrap{max-width:780px;margin:0 auto;padding:24px}
 h1{font-size:20px;color:#25d366}
 .card{background:#111b21;border:1px solid #222d34;border-radius:12px;padding:18px;margin:14px 0}
 label{display:block;font-size:13px;color:#8696a0;margin:10px 0 4px}
 input,select,textarea{width:100%;box-sizing:border-box;background:#2a3942;border:1px solid #33414b;
   color:#e9edef;border-radius:8px;padding:10px;font-size:14px}
 button{background:#25d366;color:#07130c;border:0;border-radius:8px;padding:11px 16px;font-weight:600;
   cursor:pointer;font-size:14px;margin-top:14px}
 button.sec{background:#2a3942;color:#e9edef}
 pre{background:#0b141a;border:1px solid #222d34;border-radius:8px;padding:12px;white-space:pre-wrap;
   font-size:13px;max-height:280px;overflow:auto}
 .row{display:flex;gap:10px}.row>div{flex:1}
 .badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px}
 .ok{background:#0b3d1e;color:#25d366}.pend{background:#3d340b;color:#e6c34a}.err{background:#3d0b0b;color:#ff6b6b}
 .preview{background:#005c4b;border-radius:8px;padding:10px 12px;margin:8px 0;font-size:14px;white-space:pre-wrap}
 .var{margin-top:8px}
 small.hint{color:#8696a0}
 table{width:100%;border-collapse:collapse;font-size:12px;margin-top:8px}
 th,td{border:1px solid #222d34;padding:5px 7px;text-align:left}
 th{background:#0b141a;color:#8696a0}
 code{background:#0b141a;padding:1px 5px;border-radius:4px;color:#e6c34a}
 .tabs{display:flex;gap:8px;margin:14px 0 0}
 .tab{flex:1;background:#111b21;border:1px solid #222d34;color:#8696a0;border-radius:10px 10px 0 0;
   padding:12px;cursor:pointer;font-weight:600;font-size:14px;text-align:center}
 .tab.active{background:#005c4b;color:#e9edef;border-color:#005c4b}
</style></head><body><div class="wrap">
<h1>WhatsApp Template Tester</h1>

<div class="card">
 <b>1. Templates & status</b>
 <button class="sec" onclick="listar()">Atualizar lista</button>
 <div id="tpls"></div>
</div>

<div class="tabs">
 <div class="tab active" id="tab-btn-envio" onclick="showTab('envio')">Envio 1-a-1</div>
 <div class="tab" id="tab-btn-camp" onclick="showTab('camp')">Campanha (CSV)</div>
</div>

<div class="card" id="tab-envio">
 <b>Enviar template (transacional, 1 destinatario)</b>
 <label>Telefone (com DDI, ex: +5511985743177)</label><input id="to" placeholder="+55...">
 <label>Template</label><select id="tpl" onchange="carregarTpl()"></select>
 <div id="tpldetail"></div>
 <button onclick="enviar()">Enviar</button>
 <div id="sendout"></div>
</div>

<div class="card" id="tab-camp" style="display:none">
 <b>Campanha (CSV) - disparo nativo fiel ao arquivo</b>
 <label>Template usado na campanha</label><select id="ctpl"></select>
 <div id="ctpldetail"></div>
 <div id="cfmt"></div>
 <label>Nome da campanha</label>
 <input id="cname" placeholder="ex: promo-vestibular (a data/hora e adicionada automaticamente)">
 <label>Arquivo CSV local</label>
 <input type="file" id="csvfile" accept=".csv,text/csv" onchange="lerCsv()">
 <div id="csvprev"></div>
 <button id="cbtn" onclick="dispararCampanha()" disabled>Disparar campanha (cria campanha nova + envia)</button>
 <div id="campout"></div>
</div>

<div class="card"><b>Resposta (JSON)</b><pre id="out">-</pre></div>
</div>
<script>
let CURRENT=null; // detalhe do template selecionado
function showTab(which){
  const envio=which==='envio';
  document.getElementById('tab-envio').style.display=envio?'':'none';
  document.getElementById('tab-camp').style.display=envio?'none':'';
  document.getElementById('tab-btn-envio').classList.toggle('active',envio);
  document.getElementById('tab-btn-camp').classList.toggle('active',!envio);
}
async function api(path, body){
  const o={method: body?'POST':'GET', headers:{'Content-Type':'application/json'}};
  if(body) o.body=JSON.stringify(body);
  const r=await fetch(path,o); return r.json();
}
function badge(s){const c=s==='APPROVED'?'ok':(s==='PENDING'?'pend':'err');return '<span class="badge '+c+'">'+s+'</span>'}
async function listar(){
  const d=await api('/api/templates');
  document.getElementById('out').textContent=JSON.stringify(d,null,2);
  if(d.error){document.getElementById('tpls').innerHTML='<p class="badge err">'+d.error+'</p>';return}
  let html='<ul>', sel='';
  for(const t of d.templates){
    html+='<li>'+t.name+' - '+badge(t.status)+' <small>('+t.category+'/'+t.language+')</small></li>';
    const dis = t.status!=='APPROVED' ? ' (nao aprovado)' : '';
    sel+='<option value="'+t.metaTemplateId+'">'+t.name+' ['+t.status+']'+dis+'</option>';
  }
  html+='</ul>';
  document.getElementById('tpls').innerHTML=html;
  document.getElementById('tpl').innerHTML=sel;
  document.getElementById('ctpl').innerHTML=sel;
  carregarTpl();
  carregarCtpl();
}
async function carregarTpl(){
  const id=document.getElementById('tpl').value;
  const box=document.getElementById('tpldetail');
  if(!id){box.innerHTML='';CURRENT=null;return}
  box.innerHTML='carregando definicao...';
  const d=await api('/api/template?metaTemplateId='+encodeURIComponent(id));
  document.getElementById('out').textContent=JSON.stringify(d,null,2);
  if(d.error){box.innerHTML='<p class="badge err">'+d.error+'</p>';CURRENT=null;return}
  CURRENT=d;
  let html='';
  // preview + campos por variavel, por componente
  for(const p of d.parts){
    if(p.component==='body'||p.component==='header'){
      html+='<label>'+p.component.toUpperCase()+'</label><div class="preview">'+ (p.text||'') +'</div>';
      p.indices.forEach((idx,i)=>{
        const ex=(p.examples&&p.examples[i])?p.examples[i]:'';
        html+='<div class="var"><label>Variavel {{'+idx+'}} '+
              '<small class="hint">('+p.component+')</small></label>'+
              '<input data-comp="'+p.component+'" data-idx="'+idx+'" value="'+ex.replace(/"/g,'&quot;')+'"></div>';
      });
    } else if(p.component==='footer'){
      html+='<label>FOOTER</label><div class="preview">'+(p.text||'')+'</div>';
    } else if(p.component==='buttons'){
      html+='<label>BOTOES</label><div class="preview">'+ (p.buttons||[]).join(' | ') +'</div>';
    }
  }
  const totalVars=d.parts.reduce((a,p)=>a+(p.indices?p.indices.length:0),0);
  if(totalVars===0) html+='<p><small class="hint">Este template nao tem variaveis.</small></p>';
  box.innerHTML=html;
}
async function enviar(){
  if(!CURRENT){alert('selecione um template');return}
  // coleta os valores por componente/indice
  const inputs=[...document.querySelectorAll('#tpldetail input[data-comp]')];
  const byComp={};
  for(const el of inputs){
    const c=el.getAttribute('data-comp'); const idx=parseInt(el.getAttribute('data-idx'));
    (byComp[c]=byComp[c]||[]).push({idx,val:el.value});
  }
  for(const c in byComp) byComp[c].sort((a,b)=>a.idx-b.idx);
  const body={to:document.getElementById('to').value.trim(),
    metaTemplateId:document.getElementById('tpl').value,
    name:CURRENT.name, language:CURRENT.language,
    header:(byComp.header||[]).map(x=>x.val),
    bodyVars:(byComp.body||[]).map(x=>x.val)};
  document.getElementById('sendout').innerHTML='enviando...';
  const d=await api('/api/send', body);
  document.getElementById('out').textContent=JSON.stringify(d,null,2);
  document.getElementById('sendout').innerHTML = d.error
    ? '<p class="badge err">'+d.error+'</p>'
    : '<p class="badge ok">enviado! id: '+(d.messageId||'?')+'</p>';
}
// ===== Campanha (CSV) =====
let FMT=null;        // {phone, columns, objectType, bucket}
let CSVROWS=null;    // {header:[], rows:[[]], text:string, filename:string}
document.getElementById('ctpl').addEventListener('change', carregarCtpl);

async function formatoCampanha(){
  const id=document.getElementById('ctpl').value;
  const box=document.getElementById('cfmt');
  const d=await api('/api/campaign/format'+(id?('?metaTemplateId='+encodeURIComponent(id)):''));
  if(d.error){box.innerHTML='<p class="badge err">'+d.error+'</p>';FMT=null;return}
  FMT=d;
  let h='<p><small class="hint">Campos esperados do CSV para <b>'+(d.name||'este template')+
    '</b>. Coluna obrigatoria <code>'+d.phone+'</code> = telefone do destinatario com DDI:</small></p>'+
    '<div class="preview">'+d.columns.join(',')+'</div>';
  if(d.folder) h+='<p><small class="hint">Recursos isolados deste template &rarr; pasta S3 <code>'+
    (d.bucket||'')+'/'+d.folder+'</code> · object type <code>'+(d.objectType||'')+'</code></small></p>';
  if(d.legend&&d.legend.length){
    h+='<table><thead><tr><th>coluna</th><th>variavel</th><th>onde</th><th>exemplo</th></tr></thead><tbody>';
    for(const l of d.legend)
      h+='<tr><td><code>'+l.column+'</code></td><td>'+l.placeholder+'</td><td>'+
         l.component+'</td><td>'+(l.example||'')+'</td></tr>';
    h+='</tbody></table>';
  } else {
    h+='<p><small class="hint">Este template nao tem variaveis (basta a coluna <code>phone</code>).</small></p>';
  }
  box.innerHTML=h;
  // template mudou -> invalida o CSV carregado antes
  document.getElementById('csvprev').innerHTML='';
  document.getElementById('cbtn').disabled=true; CSVROWS=null;
}
function carregarCtpl(){
  formatoCampanha();
  // mostra o corpo do template escolhido para a campanha (apenas referencia visual)
  const id=document.getElementById('ctpl').value;
  const box=document.getElementById('ctpldetail');
  if(!id){box.innerHTML='';return}
  api('/api/template?metaTemplateId='+encodeURIComponent(id)).then(d=>{
    if(d.error){box.innerHTML='<p class="badge err">'+d.error+'</p>';return}
    let h='';
    for(const p of d.parts){
      if(p.component==='body'||p.component==='header')
        h+='<label>'+p.component.toUpperCase()+'</label><div class="preview">'+(p.text||'')+'</div>';
    }
    box.innerHTML=h;
  });
}
function parseCSV(text){
  const rows=[]; let i=0,field='',row=[],inq=false;
  while(i<text.length){
    const c=text[i];
    if(inq){
      if(c==='"'){ if(text[i+1]==='"'){field+='"';i++;} else inq=false; } else field+=c;
    }else{
      if(c==='"') inq=true;
      else if(c===',') { row.push(field); field=''; }
      else if(c==='\n'||c==='\r'){ if(c==='\r'&&text[i+1]==='\n')i++; row.push(field); rows.push(row); row=[]; field=''; }
      else field+=c;
    }
    i++;
  }
  if(field!==''||row.length){ row.push(field); rows.push(row); }
  return rows.map(r=>r.map(x=>x.trim())).filter(r=>r.some(x=>x!==''));
}
function lerCsv(){
  const f=document.getElementById('csvfile').files[0];
  const box=document.getElementById('csvprev');
  document.getElementById('cbtn').disabled=true; CSVROWS=null;
  if(!f){box.innerHTML='';return}
  const rd=new FileReader();
  rd.onload=()=>{
    const text=rd.result;
    const grid=parseCSV(text);
    if(grid.length<2){box.innerHTML='<p class="badge err">CSV vazio ou sem linhas de dados</p>';return}
    const header=grid[0].map(h=>h.trim());
    const rows=grid.slice(1);
    CSVROWS={header,rows,text,filename:f.name};
    // validacao
    const phoneCol=(FMT&&FMT.phone)||'phone';
    const pIdx=header.findIndex(h=>h.toLowerCase()===phoneCol.toLowerCase());
    const known=(FMT?FMT.columns:[]).map(c=>c.toLowerCase());
    const problemas=[]; const alertas=[];
    if(pIdx<0) problemas.push('falta a coluna obrigatoria "'+phoneCol+'"');
    header.forEach(h=>{ if(known.length && !known.includes(h.toLowerCase()))
      alertas.push('coluna "'+h+'" nao mapeada (sera ignorada na ingestao)'); });
    let semTel=0;
    rows.forEach(r=>{ if(pIdx>=0 && !((r[pIdx]||'').trim())) semTel++; });
    if(semTel) problemas.push(semTel+' linha(s) sem telefone');
    // tabela (ate 20 linhas)
    let t='<table><thead><tr>'+header.map(h=>'<th>'+h+'</th>').join('')+'</tr></thead><tbody>';
    rows.slice(0,20).forEach(r=>{ t+='<tr>'+header.map((_,i)=>'<td>'+((r[i]||'')||'')+'</td>').join('')+'</tr>'; });
    t+='</tbody></table>';
    if(rows.length>20) t+='<small class="hint">... +'+(rows.length-20)+' linha(s)</small>';
    let msg='<p>'+rows.length+' contato(s).</p>';
    if(problemas.length) msg+='<p class="badge err">'+problemas.join(' | ')+'</p>';
    if(alertas.length) msg+='<p><small class="hint">'+alertas.join(' · ')+'</small></p>';
    if(!problemas.length) msg+='<p class="badge ok">CSV valido</p>';
    box.innerHTML=msg+t;
    document.getElementById('cbtn').disabled = problemas.length>0;
  };
  rd.readAsText(f);
}
async function dispararCampanha(){
  if(!CSVROWS){alert('selecione um CSV');return}
  const nome=document.getElementById('cname').value.trim();
  if(!nome){alert('informe o nome da campanha');return}
  document.getElementById('campout').innerHTML='disparando (criando campanha nova + enviando)...';
  const d=await api('/api/campaign/send',{csv:CSVROWS.text,filename:CSVROWS.filename,
    metaTemplateId:document.getElementById('ctpl').value, campaignName:nome});
  document.getElementById('out').textContent=JSON.stringify(d,null,2);
  if(d.error){document.getElementById('campout').innerHTML='<p class="badge err">'+d.error+'</p>';return}
  let m='<p class="badge ok">'+d.gravados+'/'+d.total+' perfis · '+(d.destinatarios||0)+' destinatario(s) unico(s)</p>';
  const c=d.campaign||{};
  if(c.error) m+='<p class="badge err">campanha: '+c.error+'</p>';
  else if(c.campaignId) m+='<p class="badge ok">campanha nova criada: <code>'+(c.campaignName||'')+
        '</code><br>id: <code>'+c.campaignId+'</code></p>';
  else if(c.pending) m+='<p class="badge pend">campanha NAO criada - template '+(c.status||'PENDENTE')+
        ' na Meta.</p>';
  m+='<p><small class="hint">CSV no S3: <code>'+d.s3+'</code>. Envio sai ~5-6 min apos a criacao '+
        '(minimo do schedule da API).</small></p>';
  if(d.erros&&d.erros.length) m+='<p class="badge err">'+d.erros.join(' | ')+'</p>';
  document.getElementById('campout').innerHTML=m;
}

listar();
</script></body></html>"""


class H(http.server.BaseHTTPRequestHandler):
    def _send(self, code, obj, ctype='application/json'):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.end_headers()
        if ctype == 'application/json':
            self.wfile.write(json.dumps(obj).encode('utf-8'))
        else:
            self.wfile.write(obj.encode('utf-8'))

    def log_message(self, *a):
        pass

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        u = urlparse(self.path)
        if u.path == '/' or u.path.startswith('/index'):
            return self._send(200, PAGE, 'text/html; charset=utf-8')
        if u.path == '/api/templates':
            try:
                r = sm.list_whatsapp_message_templates(id=WABA_ID)
                tpls = [{'name': t.get('templateName'), 'status': t.get('templateStatus'),
                         'category': t.get('templateCategory'), 'language': t.get('templateLanguage'),
                         'metaTemplateId': t.get('metaTemplateId')}
                        for t in r.get('templates', [])]
                return self._send(200, {'templates': tpls})
            except Exception as e:
                return self._send(200, {'error': str(e)})
        if u.path == '/api/template':
            mid = parse_qs(u.query).get('metaTemplateId', [''])[0]
            try:
                return self._send(200, template_detail(mid))
            except Exception as e:
                return self._send(200, {'error': str(e)})
        if u.path == '/api/campaign/format':
            mid = parse_qs(u.query).get('metaTemplateId', [''])[0]
            try:
                return self._send(200, campaign_columns(mid or None))
            except Exception as e:
                return self._send(200, {'error': str(e)})
        return self._send(404, {'error': 'not found'})

    def do_POST(self):
        if self.path == '/api/campaign/send':
            try:
                n = int(self.headers.get('Content-Length', 0))
                body = json.loads(self.rfile.read(n) or '{}')
                return self._send(200, campaign_send(body.get('csv', ''), body.get('filename', ''),
                                                     body.get('metaTemplateId', ''),
                                                     body.get('campaignName', '')))
            except Exception as e:
                return self._send(200, {'error': str(e)})
        if self.path != '/api/send':
            return self._send(404, {'error': 'not found'})
        try:
            n = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(n) or '{}')
            to = body['to']
            if not to.startswith('+'):
                to = '+' + to
            comps = []
            if body.get('header'):
                comps.append({'type': 'header',
                              'parameters': [{'type': 'text', 'text': v} for v in body['header']]})
            if body.get('bodyVars'):
                comps.append({'type': 'body',
                              'parameters': [{'type': 'text', 'text': v} for v in body['bodyVars']]})
            payload = {
                'messaging_product': 'whatsapp', 'recipient_type': 'individual', 'to': to,
                'type': 'template',
                'template': {'name': body['name'], 'language': {'code': body.get('language', 'pt_BR')},
                             'components': comps},
            }
            resp = sm.send_whatsapp_message(
                originationPhoneNumberId=ORIGIN,
                message=json.dumps(payload).encode('utf-8'), metaApiVersion=META_API)
            return self._send(200, {'messageId': resp.get('messageId', ''), 'ok': True,
                                    'payloadEnviado': payload})
        except Exception as e:
            return self._send(200, {'error': str(e)})


class Server(socketserver.TCPServer):
    allow_reuse_address = True


if __name__ == '__main__':
    print(f'Tester em http://127.0.0.1:{PORT}  (Ctrl+C para sair)')
    print(f'WABA={WABA_ID}  origem={ORIGIN}')
    with Server(('127.0.0.1', PORT), H) as httpd:
        httpd.serve_forever()
