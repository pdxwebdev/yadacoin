"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

from enum import Enum


class Collections(Enum):
    ASSET = "asset"
    BID = "bid"
    CONTACT = "contact"
    CALENDAR = "event_meeting"
    CHAT = "chat"
    CHAT_FILE = "chat_file"
    CONTRACT = "contract"
    CONTRACT_SIGNED = "contract_signed"
    FILE_REQUEST = "file_request"
    GENERIC = ""
    GROUP = "group"
    GROUP_CALENDAR = "group_event_meeting"
    GROUP_CHAT = "group_chat"
    GROUP_CHAT_FILE_NAME = "group_chat_file_name"
    GROUP_CHAT_FILE = "group_chat_file"
    GROUP_MAIL = "group_mail"
    MAIL = "mail"
    PERMISSION_REQUEST = "permission_request"
    SIGNATURE_REQUEST = "signature_request"
    SMART_CONTRACT = "smart_contract"
    WEB_CHALLENGE_REQUEST = "web_challenge_request"
    WEB_CHALLENGE_RESPONSE = "web_challenge_response"
    WEB_PAGE = "web_page"
    WEB_PAGE_REQUEST = "web_page_request"
    WEB_PAGE_RESPONSE = "web_page_response"
    WEB_SIGNIN_REQUEST = "web_signin_request"
    WEB_SIGNIN_RESPONSE = "web_signin_response"
