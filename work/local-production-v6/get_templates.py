"""Keep official workflow references with exact upstream revision."""
import json
from pathlib import Path
import requests
OUT = Path(__file__).resolve().parents[2] / 'outputs/local-production-v6/research'
response = requests.get('https://api.github.com/repos/Comfy-Org/workflow_templates/git/trees/main',
                        params={'recursive':'1'},timeout=30)
response.raise_for_status()
tree = response.json()
paths=[entry['path'] for entry in tree['tree'] if 'klein' in entry['path'].lower() and entry['path'].endswith('.json')]
print('REVISION',tree['sha'])
print(json.dumps(paths,indent=2))
for path in paths:
    if '4b' not in path.lower():
        continue
    response=requests.get(f'https://raw.githubusercontent.com/Comfy-Org/workflow_templates/{tree["sha"]}/{path}',timeout=30)
    response.raise_for_status()
    workflow=response.json()
    (OUT/Path(path).name).write_text(json.dumps(workflow,indent=2),encoding='utf-8')
    nodes=workflow.get('nodes',[])
    for definition in workflow.get('definitions',{}).get('subgraphs',[]):
        nodes.extend(definition.get('nodes',[]))
    print(Path(path).name,[(n['id'],n['type'],n.get('widgets_values')) for n in nodes if n['type'] not in ('MarkdownNote','Note')])
