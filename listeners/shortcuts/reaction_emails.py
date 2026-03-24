from logging import Logger

from slack_bolt import Ack
from slack_sdk import WebClient


def reaction_emails_callback(body: dict, ack: Ack, client: WebClient, logger: Logger):
    try:
        ack()

        channel_id = body["channel"]["id"]
        message_ts = body["message"]["ts"]

        result = client.reactions_get(channel=channel_id, timestamp=message_ts)
        reactions = result.get("message", {}).get("reactions", [])

        if not reactions:
            client.chat_postMessage(
                channel=channel_id,
                text="No reactions found on this message.",
            )
            return

        # Look up all unique users once
        all_user_ids = set()
        for reaction in reactions:
            all_user_ids.update(reaction.get("users", []))

        user_cache = {}
        for user_id in all_user_ids:
            try:
                user_info = client.users_info(user=user_id)
                profile = user_info.get("user", {}).get("profile", {})
                user_cache[user_id] = {
                    "name": user_info.get("user", {}).get("name", user_id),
                    "email": profile.get("email"),
                }
            except Exception as e:
                logger.warning(f"Failed to fetch info for user {user_id}: {e}")

        # Build message grouped by emoji
        sections = []
        for reaction in reactions:
            emoji = reaction.get("name", "unknown")
            mentions = []
            emails = []
            for user_id in sorted(reaction.get("users", [])):
                info = user_cache.get(user_id)
                if not info:
                    continue
                mentions.append(f"<@{user_id}>")
                if info["email"]:
                    emails.append(info["email"])
            if mentions:
                section = f":{emoji}: {', '.join(mentions)}"
                if emails:
                    section += f"\n```{', '.join(emails)}```"
                sections.append(section)

        if sections:
            text = "*Reaction emails:*\n\n" + "\n\n".join(sections)
        else:
            text = "No users found for reactions on this message."

        client.chat_postMessage(
            channel=channel_id,
            text=text,
        )
    except Exception as e:
        logger.error(e)
