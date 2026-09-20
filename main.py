name: bot
on:
  schedule:
    - cron: '*/5 * * * *'
  workflow_dispatch:
jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install --upgrade pip && pip install yfinance pandas pytz requests numpy
      - run: python main.py
        env:
          TG_TOKEN: ${{ secrets.TG_TOKEN }}
          TG_CHAT: ${{ secrets.TG_CHAT }}
