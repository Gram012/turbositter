import requests

def alert_slack(message):
    slack_api_webhook = "https://hooks.slack.com/services/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"

    requests.post(slack_api_webhook,json={"text": message}, verify=True)