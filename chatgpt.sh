#!/bin/bash
# 出力ファイルをクリア（既存の内容を削除）
echo "" > rust_files.md

# カレントディレクトリとサブディレクトリの.pyファイルを検索し、内容を出力
find . -name "*.rs" -not -path "./target/*" | while read file; do
    echo "### $file" >> rust_files.md    # ファイル名を見出しとして追加
    echo '```rust' >> rust_files.md    # rust シンタックスハイライトの開始を追加
    

    cat "$file" >> rust_files.md         # ファイルの内容を追加
    echo '```' >> rust_files.md          # シンタックスハイライトの終了を追加
done
