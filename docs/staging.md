# Yapp テスト環境（ステージング）

本番に出す前に、変更を自分だけで確認するための環境です。
Yapp のすべてのアプリ（News・お出かけ・レシピなど）で共通に使います。

## しくみ

| | 本番 | テスト環境 |
|---|---|---|
| Render サービス | 既存の Web Service | `yapp-staging`（新規） |
| ブランチ | `main` | `staging` |
| データベース | 本番DB | テスト専用（本番データには触れない） |
| 見られる人 | 全員 | アクセスキーを知っている人だけ |
| 定期処理（cron・スケジューラー） | 動く | 動かない（手動で実行） |

テスト環境では、画面の上に赤い「テスト環境」の帯が表示されます。
検索エンジンにも載りません。

## 最初の1回だけ：Render の設定

1. Render で **New → Web Service** を選び、`YahanZHANG/yahan-app` を選ぶ
2. 次のように設定する
   - Name: `yapp-staging`
   - Branch: `staging`
   - Build Command: `./build.sh`（本番と同じ）
   - Start Command: `./start_staging.sh`
3. 環境変数（Environment）を設定する
   - 本番の環境変数をコピーする。ただし **`DATABASE_URL` と `DATABASE_PATH` はコピーしない**
     （テスト環境は自分専用の SQLite で動き、本番データを変更しない）
   - 追加する変数:
     - `APP_ENV` = `staging`
     - `STAGING_ACCESS_KEY` = 長いランダムな文字列（パスワードのようなもの）
     - `DEBUG` = `False`
   - 本番と同じ `SECRET_KEY` は使わず、別の値にする
4. Cron Job は**作らない**（ニュースの自動更新や通知の自動送信を起こさないため）

無料プランのサービスは、しばらく使わないと止まり、ディスクの内容も消えます。
テスト用なので問題ありませんが、データが消えたら下の「データを入れる」をやり直してください。

## はじめてアクセスするとき

ブラウザで次のURLを一度開きます。

```
https://yapp-staging.onrender.com/?staging_key=<STAGING_ACCESS_KEY の値>
```

これで端末に許可が保存され、1年間はキーなしで見られます。
キーなしで開くと「関係者専用です」と表示されます。

iPhone でホーム画面に追加して試す場合は、Safari で上のURLを開いたあとに
「ホーム画面に追加」してください（Safari の Cookie がアプリにコピーされます）。

## データを入れる

テスト環境のデータベースは空から始まります。
Render の `yapp-staging` の **Shell** で必要なものを実行します。

```bash
# 管理者ユーザー
python manage.py createsuperuser

# SwissNews のニュースを1回取り込む（OpenAI の料金がかかる）
python manage.py refresh_news --period morning
```

`--period` を付けると、更新後にPush通知も送られます。
送り先はテスト環境で通知をONにした端末だけです（本番のユーザーには届きません）。

`seed_master_data` と `setup_news_defaults` は起動時に自動で実行されます。

## 変更をテストする流れ

1. 変更ごとにブランチを作り、PR を出す（いつも通り）
2. そのブランチを `staging` に取り込む

   ```bash
   git checkout staging
   git pull origin staging
   git merge origin/<変更のブランチ>
   git push origin staging
   ```

   Render が `staging` を自動でデプロイする
3. テスト環境で画面と機能を確認する
4. 問題なければ PR を `main` にマージ（ここで本番に反映）

### staging をきれいにする

いくつも試したあと、`staging` を本番と同じ状態に戻したいときは:

```bash
git checkout staging
git reset --hard origin/main
git push --force origin staging
```

`staging` はテスト専用のブランチなので、強制的に上書きしても問題ありません。
`main` には絶対に `--force` を使わないでください。

## 定期処理を試したいとき

お出かけアプリのスケジューラーなど、普段は止めている定期処理を動かしたい場合は、
環境変数 `STAGING_RUN_SCHEDULERS=true` を追加して再デプロイします。
外部APIの利用料がかかることがあるので、確認が終わったら消してください。
