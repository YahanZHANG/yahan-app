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
| 定期処理（cron・スケジューラー） | 動く | 動かない |
| 料金 | 有料プラン | 無料 |

テスト環境では、画面の上に赤い「テスト環境」の帯が表示されます。
検索エンジンにも載りません。

## 最初の1回だけ：Render の設定

Render の **Free（無料）インスタンス**で動かします。料金はかかりません。

1. Render で **New → Web Service** を選び、`YahanZHANG/yahan-app` を選ぶ
2. 次のように設定する
   - Name: `yapp-staging`
   - Branch: `staging`
   - Instance Type: **Free**
   - Build Command: `./build.sh`（本番と同じ）
   - Start Command: `./start_staging.sh`
3. 環境変数（Environment）を設定する
   - 本番の環境変数をコピーする。ただし **`DATABASE_URL` と `DATABASE_PATH` はコピーしない**
     （テスト環境は自分専用の SQLite で動き、本番データを変更しない）
   - 値を変える変数:
     - `DEBUG` = `False`
     - `SECRET_KEY` = 本番とは別のランダムな文字列
   - 追加する変数:
     - `APP_ENV` = `staging`
     - `STAGING_ACCESS_KEY` = 自分で決める合言葉（英字と数字だけ。URLに入れるため）
     - `DJANGO_SUPERUSER_USERNAME` / `DJANGO_SUPERUSER_EMAIL` / `DJANGO_SUPERUSER_PASSWORD`
       = テスト環境の管理者アカウント（起動時に自動で作られる）
     - `STAGING_LOAD_NEWS` = `true`（SwissNews を試すときだけ。下の説明を参照）
     - `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` / `VAPID_CONTACT_EMAIL`（Push通知を試すとき）
4. Cron Job は**作らない**（ニュースの自動更新や通知の自動送信を起こさないため）

### 無料インスタンスの注意

- 15分アクセスがないと止まり、次に開いたとき1分ほどで起動する
- 止まるたびにデータベースは空に戻る（起動時に必要なデータは自動で用意される）
- Shell は使えない（必要な準備は `start_staging.sh` が自動で行う）
- メール送信（Gmail）はできない。エラー通知メールはテスト環境からは届かない
- 無料枠は月750時間。止まっている時間は数えないので、テスト用途なら足りる

## はじめてアクセスするとき

ブラウザで次のURLを一度開きます。

```
https://yapp-staging.onrender.com/?staging_key=<STAGING_ACCESS_KEY の値>
```

これで端末に許可が保存され、1年間はキーなしで見られます。
キーなしで開くと「関係者専用です」と表示されます。

iPhone でホーム画面に追加して試す場合は、Safari で上のURLを開いたあとに
「ホーム画面に追加」してください（Safari の Cookie がアプリにコピーされます）。

## SwissNews のデータ

`STAGING_LOAD_NEWS=true` のとき、起動するたびに裏でニュースを取り込みます
（OpenAI の料金がかかるので、翻訳は最大60件。`STAGING_NEWS_AI_LIMIT` で変更可）。
起動してから数分でニュースが表示されます。

取り込みのあとはPush通知も送られますが、送り先はテスト環境で通知をONにした端末だけです
（本番のユーザーには届きません）。

SwissNews の確認が終わったら `STAGING_LOAD_NEWS` を消してください。

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
