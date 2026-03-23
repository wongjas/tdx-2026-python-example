import logging
from unittest.mock import Mock

from slack_bolt import Ack
from slack_sdk import WebClient

from listeners.shortcuts.reaction_emails import reaction_emails_callback


test_logger = logging.getLogger(__name__)


def _make_body(channel_id="C123", message_ts="1234567890.123456", user_id="U999"):
    return {
        "channel": {"id": channel_id},
        "message": {"ts": message_ts},
        "user": {"id": user_id},
    }


def _make_user_info(name, email=None):
    profile = {"email": email} if email else {}
    return {"user": {"name": name, "profile": profile}}


class TestReactionEmails:
    def setup_method(self):
        self.fake_ack = Mock(Ack)
        self.fake_client = Mock(WebClient)
        self.fake_client.reactions_get = Mock()
        self.fake_client.users_info = Mock()
        self.fake_client.chat_postEphemeral = Mock()
        self.fake_body = _make_body()

    def test_happy_path(self):
        self.fake_client.reactions_get.return_value = {
            "message": {
                "reactions": [
                    {"name": "thumbsup", "users": ["U001", "U002"]},
                    {"name": "heart", "users": ["U002", "U003"]},
                ]
            }
        }
        self.fake_client.users_info.side_effect = lambda user: {
            "U001": _make_user_info("alice", "alice@example.com"),
            "U002": _make_user_info("bob", "bob@example.com"),
            "U003": _make_user_info("carol", "carol@example.com"),
        }[user]

        reaction_emails_callback(
            body=self.fake_body, ack=self.fake_ack, client=self.fake_client, logger=test_logger
        )

        self.fake_ack.assert_called_once()
        self.fake_client.reactions_get.assert_called_once_with(
            channel="C123", timestamp="1234567890.123456"
        )
        assert self.fake_client.users_info.call_count == 3
        kwargs = self.fake_client.chat_postEphemeral.call_args.kwargs
        assert kwargs["channel"] == "C123"
        assert kwargs["user"] == "U999"
        text = kwargs["text"]
        # Grouped by emoji with linked mentions
        assert ":thumbsup:" in text
        assert ":heart:" in text
        assert "<@U001>" in text
        assert "<@U002>" in text
        assert "<@U003>" in text
        # Emails in code blocks for copy-pasting
        assert "alice@example.com" in text
        assert "bob@example.com" in text
        assert "carol@example.com" in text

    def test_no_reactions(self):
        self.fake_client.reactions_get.return_value = {
            "message": {"reactions": []}
        }

        reaction_emails_callback(
            body=self.fake_body, ack=self.fake_ack, client=self.fake_client, logger=test_logger
        )

        self.fake_ack.assert_called_once()
        self.fake_client.users_info.assert_not_called()
        kwargs = self.fake_client.chat_postEphemeral.call_args.kwargs
        assert "No reactions found" in kwargs["text"]

    def test_missing_reactions_key(self):
        self.fake_client.reactions_get.return_value = {"message": {}}

        reaction_emails_callback(
            body=self.fake_body, ack=self.fake_ack, client=self.fake_client, logger=test_logger
        )

        self.fake_ack.assert_called_once()
        self.fake_client.users_info.assert_not_called()
        kwargs = self.fake_client.chat_postEphemeral.call_args.kwargs
        assert "No reactions found" in kwargs["text"]

    def test_user_without_email(self):
        self.fake_client.reactions_get.return_value = {
            "message": {
                "reactions": [{"name": "wave", "users": ["U001", "U002"]}]
            }
        }
        self.fake_client.users_info.side_effect = lambda user: {
            "U001": _make_user_info("alice", "alice@example.com"),
            "U002": _make_user_info("bob", None),
        }[user]

        reaction_emails_callback(
            body=self.fake_body, ack=self.fake_ack, client=self.fake_client, logger=test_logger
        )

        kwargs = self.fake_client.chat_postEphemeral.call_args.kwargs
        text = kwargs["text"]
        # Both users mentioned
        assert "<@U001>" in text
        assert "<@U002>" in text
        # Only alice's email in the code block
        assert "alice@example.com" in text
        assert "bob@example.com" not in text

    def test_user_lookup_failure(self, caplog):
        self.fake_client.reactions_get.return_value = {
            "message": {
                "reactions": [{"name": "rocket", "users": ["U001", "U002"]}]
            }
        }

        def users_info_side_effect(user):
            if user == "U001":
                return _make_user_info("alice", "alice@example.com")
            raise Exception("user_not_found")

        self.fake_client.users_info.side_effect = users_info_side_effect

        with caplog.at_level(logging.WARNING):
            reaction_emails_callback(
                body=self.fake_body, ack=self.fake_ack, client=self.fake_client, logger=test_logger
            )

        kwargs = self.fake_client.chat_postEphemeral.call_args.kwargs
        assert "alice@example.com" in kwargs["text"]
        # Failed user not mentioned
        assert "<@U002>" not in kwargs["text"]
        assert "user_not_found" in caplog.text

    def test_ack_exception(self, caplog):
        self.fake_ack.side_effect = Exception("ack failed")

        with caplog.at_level(logging.ERROR):
            reaction_emails_callback(
                body=self.fake_body, ack=self.fake_ack, client=self.fake_client, logger=test_logger
            )

        self.fake_ack.assert_called_once()
        self.fake_client.reactions_get.assert_not_called()
        assert "ack failed" in caplog.text

    def test_deduplication_across_reactions(self):
        self.fake_client.reactions_get.return_value = {
            "message": {
                "reactions": [
                    {"name": "thumbsup", "users": ["U001"]},
                    {"name": "heart", "users": ["U001"]},
                    {"name": "rocket", "users": ["U001"]},
                ]
            }
        }
        self.fake_client.users_info.return_value = _make_user_info("alice", "alice@example.com")

        reaction_emails_callback(
            body=self.fake_body, ack=self.fake_ack, client=self.fake_client, logger=test_logger
        )

        # Only one users_info call despite user appearing in 3 reactions
        self.fake_client.users_info.assert_called_once_with(user="U001")
        kwargs = self.fake_client.chat_postEphemeral.call_args.kwargs
        text = kwargs["text"]
        assert ":thumbsup:" in text
        assert ":heart:" in text
        assert ":rocket:" in text
        # User appears under each emoji section
        assert text.count("<@U001>") == 3

    def test_all_users_missing_email(self):
        self.fake_client.reactions_get.return_value = {
            "message": {
                "reactions": [{"name": "wave", "users": ["U001", "U002"]}]
            }
        }
        self.fake_client.users_info.side_effect = lambda user: {
            "U001": _make_user_info("alice", None),
            "U002": _make_user_info("bob", None),
        }[user]

        reaction_emails_callback(
            body=self.fake_body, ack=self.fake_ack, client=self.fake_client, logger=test_logger
        )

        kwargs = self.fake_client.chat_postEphemeral.call_args.kwargs
        text = kwargs["text"]
        # Users still mentioned
        assert "<@U001>" in text
        assert "<@U002>" in text
        # No code block since no emails
        assert "```" not in text
