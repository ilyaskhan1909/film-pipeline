"""Read-only account/API and official remote MCP checks. Never prints credentials."""
import json, sys
from pathlib import Path
import requests

TOKEN_PATH=Path('C:/Users/ilyas/.kaggle/access_token')
ORIGIN='https://www.kaggle.com'
report={'credential_source':'existing local access_token file','browser_used':False,
        'account_mutations':False,'notebook_mutations':False}

def rpc_payload(response):
    if 'text/event-stream' in response.headers.get('Content-Type',''):
        for block in response.text.split('\n\n'):
            data='\n'.join(line[5:].lstrip() for line in block.splitlines() if line.startswith('data:'))
            if data:
                try: return json.loads(data)
                except json.JSONDecodeError: pass
        raise ValueError('No JSON-RPC message')
    return response.json()

try:
    token=TOKEN_PATH.read_text(encoding='utf-8-sig').strip()
    if not token: raise ValueError('Empty credential file')
    response=requests.post(ORIGIN+'/api/v1/oauth2/introspect',json={'token':token},timeout=(10,35))
    report['api_http_status']=response.status_code
    response.raise_for_status()
    auth=response.json()
    report['api_authenticated']=bool(auth.get('active'))
    if auth.get('active'):
        report['username']=auth.get('username')
        headers={'Authorization':'Bearer '+token,'Content-Type':'application/json',
                 'Accept':'application/json, text/event-stream'}
        result=requests.post(ORIGIN+'/mcp',headers=headers,json={'jsonrpc':'2.0','id':1,'method':'initialize',
            'params':{'protocolVersion':'2025-06-18','capabilities':{},
                      'clientInfo':{'name':'codex-kaggle-access-check','version':'1.0'}}},timeout=(10,35))
        report['mcp_http_status']=result.status_code
        result.raise_for_status()
        initialized=rpc_payload(result)
        if 'error' in initialized:
            report['mcp_error_code']=initialized['error'].get('code')
        else:
            protocol=initialized['result']['protocolVersion']
            headers['MCP-Protocol-Version']=protocol
            if result.headers.get('Mcp-Session-Id'): headers['Mcp-Session-Id']=result.headers['Mcp-Session-Id']
            notice=requests.post(ORIGIN+'/mcp',headers=headers,json={'jsonrpc':'2.0','method':'notifications/initialized'},timeout=(10,35))
            notice.raise_for_status()
            listed=requests.post(ORIGIN+'/mcp',headers=headers,json={'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}},timeout=(10,35))
            listed.raise_for_status()
            payload=rpc_payload(listed)
            if 'error' in payload:
                report['mcp_error_code']=payload['error'].get('code')
            else:
                tools=payload['result'].get('tools',[])
                report.update(mcp_connected=True,mcp_protocol=protocol,mcp_tool_count=len(tools),
                    notebook_tool_names=[t['name'] for t in tools if any(w in t['name'].lower() for w in ('kernel','notebook'))])
    print(json.dumps(report,ensure_ascii=False,indent=2))
    sys.exit(0 if report.get('api_authenticated') else 1)
except requests.RequestException as exc:
    report['error_type']=type(exc).__name__
    if getattr(exc,'response',None) is not None: report['failed_http_status']=exc.response.status_code
    # Do not print exception text, request headers/bodies, token or raw auth responses.
    print(json.dumps(report,ensure_ascii=False,indent=2)); sys.exit(2)
except Exception as exc:
    report['error_type']=type(exc).__name__
    print(json.dumps(report,ensure_ascii=False,indent=2)); sys.exit(3)
