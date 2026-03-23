from slack_bolt import App
from .reaction_emails import reaction_emails_callback


def register(app: App):
    app.shortcut("reaction_emails_shortcut")(reaction_emails_callback)
