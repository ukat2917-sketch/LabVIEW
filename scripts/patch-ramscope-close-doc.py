from pathlib import Path

chapter = Path('docs/10_RAMScope実装方針.md')
staged = Path('docs/_tmp_RAMScope_File_Log_Close_detail.md')
text = chapter.read_text(encoding='utf-8')
detail = staged.read_text(encoding='utf-8').strip() + '\n'

if '<!-- ramscope-close-detail-start -->' in text:
    raise SystemExit('close detail already merged')

anchor = '#### 9. テスト\n\n正常Close、前段error付きClose、無効Ref、二重Close、Flush error、Close error。\n'
if anchor not in text:
    raise SystemExit('10.12.5 anchor not found')

text = text.replace(anchor, anchor + '\n' + detail, 1)
chapter.write_text(text, encoding='utf-8')
print('merged close detail')
