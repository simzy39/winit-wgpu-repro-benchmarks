from pathlib import Path
H=Path(__file__).resolve().parent
s=(H/'check_final_source.py').read_text()
s=s.replace('final-source-','backoff-source-').replace('FINAL_SOURCE_CHECKS_COMPLETE','BACKOFF_SOURCE_CHECKS_COMPLETE')
exec(compile(s,str(H/'check_final_source.py'),'exec'))
