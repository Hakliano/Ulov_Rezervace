from unittest.mock import MagicMock, patch

from django.test import TestCase

from jadro.mail_imap import MailError, _folder_uidvalidity, _imap_mailbox_arg


class FolderSelectLogTests(TestCase):
    @patch('jadro.mail_imap.logger')
    def test_select_fail_logs_imap_response(self, log_mock):
        client = MagicMock()
        client.select.return_value = ('NO', [b'[NONEXISTENT] Unknown Mailbox'])
        client._quote.side_effect = lambda s: f'"{s}"'
        with self.assertRaisesMessage(MailError, 'Složku nelze otevřít.'):
            _folder_uidvalidity(client, 'INBOX.Sent Items')
        client.select.assert_called_once_with('"INBOX.Sent Items"', readonly=True)
        log_mock.warning.assert_called_once_with(
            'IMAP SELECT selhalo folder=%r typ=%s data=%s',
            'INBOX.Sent Items',
            'NO',
            '[NONEXISTENT] Unknown Mailbox',
        )

    def test_mailbox_arg_quotes_spaces(self):
        client = MagicMock()
        client._quote.side_effect = lambda s: f'"{s}"'
        self.assertEqual(_imap_mailbox_arg(client, 'INBOX.Sent Items'), '"INBOX.Sent Items"')
        self.assertEqual(_imap_mailbox_arg(client, 'INBOX'), 'INBOX')
        client._quote.assert_called_once_with('INBOX.Sent Items')

    @patch('jadro.mail_imap.logger')
    def test_select_ok_no_log(self, log_mock):
        client = MagicMock()
        client.select.return_value = ('OK', [b'1'])
        client.response.return_value = ('OK', [b'42'])
        self.assertEqual(_folder_uidvalidity(client, 'INBOX'), '42')
        log_mock.warning.assert_not_called()