# Stream Audio Monitor

YouTubeへ投稿した後の音の印象を、投稿前に確認するためのWindows用リアルタイム音声モニターです。

主な目的は、制作中の音をYouTubeのOpus圧縮・再生音量補正・スマホ再生へ近づけて確認することです。

## 必要なもの

- Python 3.14 などのPython 3
- FFmpeg（実Opus／AACプレビューとWAV書き出しに使用）
- `requirements.txt` のライブラリ

起動:

```powershell
python main.py
```

## ふだんの使い方

1. InputとOutputを選び、`Start` を押します。
2. 曲を再生する前に `Reset LUFS-I` を押します。CLIP表示も同時にリセットされます。
3. `YouTube` プリセットを押します。
4. 必要に応じて `Phone Speaker Preview`、`Mono Preview`、`Bass Mono (150 Hz)` をONにします。
5. 画面上部の `YT` 表示で、YouTube想定の再生音量を確認します。

## よく使うプレビュー

| 操作 | 確認できること |
| --- | --- |
| YouTube Opus Preview | YouTube向けOpus圧縮後の印象 |
| YouTube Playback Normalize | YouTubeで大きい曲だけ下がる再生音量 |
| Phone Speaker Preview | スマホスピーカー風のモノラル・帯域制限 |
| Mono Preview | 完全モノラルでの互換性 |
| Bass Mono (150 Hz) | キック／ベースの低域モノ互換性 |
| Bypass Effects | 加工前の元入力との比較 |
| Mute Monitor | 音だけ消してメーター測定を続ける |

## YouTubeの音量確認

`YT: -0.9 dB / 90%` の場合、YouTube再生時に約0.9 dB下がり、再生音量は約90%になる想定です。

`YouTube Playback Normalize` がONの時だけ、リアルタイム試聴でこの音量低下を再現します。静かな曲を自動で大きくする処理は行いません。

## 実際の投稿結果で校正する

投稿済みのYouTube動画の「統計情報」に `100% / 71%` のような表示がある場合:

1. `Calibrate YouTube` を押します。
2. その動画に使用した元WAVを選びます。
3. 後ろの数値（例: `71`）を入力します。

`YT Ref` が更新され、今後のリアルタイム試聴・WAV解析・書き出しに使われます。誤って調整した場合は `Reset YT Ref` で標準の `-14.0 LUFS` に戻せます。

## WAV書き出し

- `Export Opus WAV`: OpusプレビューWAVを1つ作成
- `Export AAC WAV`: AACプレビューWAVを1つ作成
- `Export YouTube A/B`: Opusのみ版と、Opus＋YouTube音量版を作成
- `Export Codec Pack`: Opus＋YouTube音量版と、AAC＋YouTube音量版をまとめて作成

`Apply YouTube Volume` は単体のOpus／AAC書き出しにだけ適用されます。A/BとCodec Packは常にYouTube想定音量版を作成します。

## 注意

このソフトはYouTube内部の非公開処理を完全再現するものではなく、投稿前判断のための実用的な近似です。最終的には実際の投稿動画と比較して、`Calibrate YouTube` で自分の環境に合わせてください。
