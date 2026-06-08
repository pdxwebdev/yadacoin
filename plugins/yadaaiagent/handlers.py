"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

yadaaiagent handlers.py -- thin entry point; imports all handlers from focused
sub-modules and exposes the HANDLERS route table.
"""

import os

import tornado.web

from .backend.agent.handlers import (
    AgentAuthAppHandler,
    AgentChallengeHandler,
    AgentChatHandler,
    AgentDiscoverHandler,
    AgentListHandler,
    AgentRegisterHandler,
    BookingContextHandler,
    WellKnownDidHandler,
)
from .backend.booking.handlers import TravelBookingHandler, _vendor_routes
from .backend.microsoft.handlers import MicrosoftExecuteHandler
from .backend.node.config import NodeConfigApplyHandler
from .backend.oauth.handlers import (
    OAuthDevicePollHandler,
    OAuthDeviceStartHandler,
    OAuthMeHandler,
    OAuthSessionBindHandler,
    RekeySessionsHandler,
)
from .backend.sia.handlers import SiaDownloadHandler
from .backend.wallet.handlers import (
    CredentialReceiptResyncHandler,
    FindRecoveryTipHandler,
    WalletInfoHandler,
    WalletSendHandler,
)

HANDLERS = [
    (r"/.well-known/did.json", WellKnownDidHandler),
    (r"/contexts/booking/v1", BookingContextHandler),
    (
        r"/ai-agent-auth/assets/(.*)",
        tornado.web.StaticFileHandler,
        {"path": os.path.join(os.path.dirname(__file__), "dist", "assets")},
    ),
    (r"/ai-agent-auth", AgentAuthAppHandler),
    (r"/ai-agent-auth/", AgentAuthAppHandler),
    (r"/ai-agent-auth/api/agents/register", AgentRegisterHandler),
    (r"/ai-agent-auth/api/agents/discover", AgentDiscoverHandler),
    (r"/ai-agent-auth/api/agents", AgentListHandler),
    (r"/ai-agent-auth/api/chat", AgentChatHandler),
    (r"/ai-agent-auth/api/challenge", AgentChallengeHandler),
    (r"/ai-agent-auth/api/node-config/apply", NodeConfigApplyHandler),
    (r"/ai-agent-auth/api/wallet/info", WalletInfoHandler),
    (r"/ai-agent-auth/api/wallet/send", WalletSendHandler),
    (r"/ai-agent-auth/api/oauth/([a-z]+)/device/start", OAuthDeviceStartHandler),
    (r"/ai-agent-auth/api/oauth/([a-z]+)/device/poll", OAuthDevicePollHandler),
    (r"/ai-agent-auth/api/oauth/([a-z]+)/session/bind", OAuthSessionBindHandler),
    (r"/ai-agent-auth/api/oauth/([a-z]+)/me", OAuthMeHandler),
    (r"/ai-agent-auth/api/microsoft/execute", MicrosoftExecuteHandler),
    (r"/ai-agent-auth/api/rekey-sessions", RekeySessionsHandler),
    (r"/ai-agent-auth/api/find-recovery-tip", FindRecoveryTipHandler),
    (r"/ai-agent-auth/api/resync-credentials", CredentialReceiptResyncHandler),
    (r"/ai-agent-auth/api/travel", TravelBookingHandler),
    (r"/ai-agent-auth/sia/download/([^/]+)", SiaDownloadHandler),
    *_vendor_routes,
]
