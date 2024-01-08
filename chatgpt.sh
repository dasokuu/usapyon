#!/bin/bash
# 出力ファイルをクリア（既存の内容を削除）
echo "" > python_files.md

# カレントディレクトリとサブディレクトリの.pyファイルを検索し、内容を出力
find . -name "*.py" | while read file; do
    echo "### $file" >> python_files.md    # ファイル名を見出しとして追加
    echo '```python' >> python_files.md    # Python シンタックスハイライトの開始を追加
    cat "$file" >> python_files.md         # ファイルの内容を追加
    echo '```' >> python_files.md          # シンタックスハイライトの終了を追加
done

echo 'このアプリケーションを100点満点で採点し、修正案のコードを示してください。' >> python_files.md
