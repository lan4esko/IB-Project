#!/usr/bin/env python3
"""Offline checks of docs structure/links. No network, no secrets or root required."""
from pathlib import Path
import re, sys
DOCS = Path(__file__).resolve().parents[1]
required = [
 'README.md','00-FIRST-RESPONSE.md','01-SYSTEM-REGISTER.md','02-TOPOLOGY.md',
 '03-ARCHITECTURE.md','04-COMPONENT-SPEC.md','RELEASES.md','CHANGELOG.md',
 'DOCUMENTATION-POLICY.md','REFERENCES.md','operations/START-STOP.md',
 'operations/DAILY-RUNBOOK.md','operations/INCIDENTS.md','operations/DIAGNOSTIC-TREE.md',
 'operations/BACKUP.md','operations/RESTORE-DR.md','operations/SECURITY-AIRGAP.md',
 'operations/GIT-RELEASES.md','operations/UPGRADE.md',
 'systems/OI-REGISTRY.md','systems/OPENPROJECT.md','systems/IB-PLATFORM.md',
 'systems/RAG-LLM.md','systems/GOVSEC-CORPUS.md','systems/AI-DEV-WORKFLOWS.md','integrations/OPENPROJECT-API.md',
 'integrations/SMB-AD-ROADMAP.md','data/OI-DATA-MODEL.md','data/DOCUMENTS.md',
 'diagrams/01-zgt-context.mmd','diagrams/02-oi-deployment.mmd',
 'diagrams/03-process-and-data.mmd', 'templates/RELEASE-CHECKLIST.md',
 'scripts/collect_inventory.sh', 'scripts/pre-commit-docs.sh',
]
problems=[]
for f in required:
 if not (DOCS/f).is_file(): problems.append('missing: '+f)
# Restrict to Markdown local links; no need to fetch any URL.
link=re.compile(r'(?<!!)\[[^\]]+\]\(([^)]+)\)')
for md in DOCS.rglob('*.md'):
 if 'local' in md.relative_to(DOCS).parts and md.name != 'README.md':
  continue
 data=md.read_text(encoding='utf-8')
 for match in link.finditer(data):
  target=match.group(1).strip().split(' ',1)[0]
  if target.startswith(('#','http://','https://','mailto:','sandbox:')): continue
  target=target.split('#',1)[0].split('?',1)[0]
  if not target: continue
  file=(md.parent/target).resolve()
  if not file.exists(): problems.append(f'bad link: {md.relative_to(DOCS)} -> {target}')
# This scan catches only common accidental secret literals, never full DLP.
for f in DOCS.rglob('*.md'):
 if 'references' in f.relative_to(DOCS).parts: continue
 for i,line in enumerate(f.read_text(encoding='utf-8').splitlines(),1):
  if re.search(r'(?i)\b(?:OI_DB_PASSWORD|OI_SESSION_SECRET|OPENPROJECT_API_KEY|OI_OP_API_KEY)\s*=\s*[A-Za-z0-9_+/=]{24,}\s*$',line):
   problems.append(f'possible embedded secret: {f.relative_to(DOCS)}:{i}')
if problems:
 print('DOCS CHECK FAILED:')
 for p in problems:print(' - '+p)
 sys.exit(1)
files=sum(1 for _ in DOCS.rglob('*.md'))
print(f'DOCS CHECK OK: {files} Markdown files, required structure and relative links valid')
