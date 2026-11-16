# 設計

## 目的

- 人間の今の状態、位置、コーディング、サービスとマシンの死活を 1 枚のページで公開する
- 公開される情報は collector が書く `status.json` 1 つだけにする。丸めと除外はすべて collector で行い、frontend は表示だけを行う
- 作業の中身 (タスク名、project 名) と座標はページにもデータにも出さない
- 取得元の 1 つが落ちても、ほかは更新を続ける

## 作らないもの

- uptime の履歴 (稼働率、過去の障害)
- 市区町村や座標の表示
- HTTP の push 受信口。push は ssh の forced command で受ける

## 人間の状態

送る側は、状態が変わったときと一定間隔 (5 分) で `<category> <since-epoch>` を送る。変わらなくても送るのは、ページが「10 分届かなければ offline」と判定するため。

`kisenone-status-push` は `SSH_ORIGINAL_COMMAND` を読む。受け付けるのは決まったカテゴリ 8 つと、7 日前より新しく 1 分後より古い epoch 秒だけで、それ以外は exit 1 で何も書かない。鍵には `command="…",restrict` を付けるので、シェルもポート転送も使えない。

- `human.json`: 今の状態、その状態になった時刻、受け取った時刻、エージェントの数と ssh 先につながったか (どちらも省略可)
- `human.log`: 受け取った時刻・カテゴリ・エージェントの数 (空なら未指定) をタブ区切りで 1 行ずつ。2 日より古い行は捨てる

「AI の並走時間」は、当日の `delegating` と `computering` の時間の和のうち、`delegating` かエージェントが 1 以上だった時間の割合。各行のカテゴリは次の行まで続いたものとし、10 分より長い空白は数えない (PC が止まっていた)。合計が 1 分未満なら出さない。push は `<category> <since> [<agents 0-99> [<remote 0|1>]]`。`remote` は、送ってくるマシンが直近に ssh 先につながったか (「マシン」の節)。

## 位置

Dawarich の `GET /api/v1/points` から、最新の 1 点と当日の点を取る。`X-Forwarded-Proto: https` を付ける (Dawarich は https を強制し、loopback の http ではリダイレクトされる)。

- 都道府県: 国土数値情報を 1% に簡略化した境界で point-in-polygon。多角形に入らなくても 3 km 以内なら一番近い都道府県にする (埋立地、海岸線の簡略化の誤差)。Natural Earth 10m の admin-1 は東京都と神奈川県の境 (武蔵小杉、相模大野) を誤判定したので使わない
- 国: Natural Earth 50m admin-0。コードは `ISO_A2_EH`。`-99` (未承認の地域など) は `null`
- 今日の移動距離: 当日の点の間の haversine 距離の和。`accuracy` が 100 m を超える点は除く
- 移動中: 最新の 2 点の間の速度が 15 km/h 以上で、最新の点が 15 分以内
- 時間帯: Natural Earth 10m の time zones の多角形に最新の点が入るかで、UTC からの差 (分) を `utc_offset_minutes` に入れる。海上などで入らなければ `null`。夏時間は見ない (frontend の現地時刻は、夏時間の間 1 時間ずれる)

## コーディング

Wakapi の `GET /api/summary?interval=today` (`Authorization: Bearer <base64(api key)>`)。合計秒数、上位 3 言語と割合 (4 位以下は `other`)、OS の割合を出す。project、branch、machine、editor は捨てる。言語・OS の `Unknown` (エディタ以外のツールの heartbeat) は上位と OS の選出から外し、言語は合計と割合の分母に含めて時間を `other` に入れる。OS の割合は `Unknown` を除いた合計が分母で、`oses` は空になることがある。

## サービス

- `systemd`: `LoadState=loaded` で、`ActiveState=active` か、`ActiveState=inactive` かつ `Result=success` (timer で動く oneshot が成功して終わった後)
- `http`: 2xx / 3xx。タイムアウト 5 秒。ヘッダを足せる
- `tcp`: 5 秒以内に接続できる

並列に確かめる。`private` は名前と状態だけ、`eventOnly` は down のとき灰色で `event only` と出す。

## マシン

サービスと同じ `systemd` / `http` / `tcp` に `push` を足す。名前と状態だけを出す。

- `push` の `self`: 状態を push してくるマシン。最後の push が 10 分 (600 秒) 以内なら up、それ以外 (push が無いときも) は down
- `push` の `remote`: push してくるマシンが 4 語目で報告する ssh 先。最後の push が 10 分より古いか、4 語目が無ければ `null` (分からない)。frontend は灰色で `unknown` と出す

collector が動いているマシンと、それを載せている host は、落ちるとページが更新されなくなるので down とは出ない。そのときは `status.json` が古くなり、ページ全体が薄くなる。

## `status.json`

```json
{
  "v": 2,
  "generated_at": "2026-11-15T12:00:00+09:00",
  "human": { "state": "computering", "since": "…", "pushed_at": "…", "agents": 2, "ai_ratio_today": 0.62 },
  "location": { "country": "JP", "pref": "東京都", "utc_offset_minutes": 540, "moving": false, "today_km": 12.3, "point_at": "…", "at": "…" },
  "code": { "today_sec": 11520, "langs": [["Nix", 0.52], ["TypeScript", 0.3], ["Go", 0.1], ["other", 0.08]], "oses": [["Linux", 0.9], ["Darwin", 0.1]], "at": "…" },
  "services": [
    { "name": "blog", "url": "https://…", "up": true, "checked_at": "…" },
    { "name": "db", "private": true, "up": true, "checked_at": "…" }
  ],
  "machines": [
    { "name": "nas", "up": true, "checked_at": "…" },
    { "name": "laptop", "up": null, "checked_at": "…" }
  ]
}
```

- 時刻は ISO 8601 (設定したオフセット、既定 JST)。「3 分前」のような表示用の文字列は入れない
- `at` / `checked_at` は最後に取得に成功した時刻。`point_at` は最後に記録された点の時刻
- 取得に失敗したセクションは、前回の値と時刻をそのまま残す。取得に成功して「点が無い」になったときは `null`
- 設定していない取得元 (URL か API キーが無い) のセクションは出さない
- 一時ファイルに書いてから rename で置き換える

## 配信

nginx が frontend (Nix store) と `status.json` を配信する。`status.json` は `Cache-Control: public, max-age=30` と `Access-Control-Allow-Origin: *`、ほかは `max-age=300`。

## 検討して採らなかったもの

- dashboard (glance など) の公開: 作者が見るためのもので、認証は全ページ共通。一部だけ公開できない
- collector が HTML を出す: デザインを変えるたびに collector を直すことになる
- Astro / Vite: カード数枚のページには要らない
- 逆ジオコーディングの外部 API: 座標を外に送ることになる
- HTTP の push 受信口: 認証を自分で作ることになる。ssh の forced command で足りる
