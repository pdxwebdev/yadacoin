import json
import hashlib
from pyfcm import FCMNotification

class PushNotification(object):
    def __init__(self, config):
        self.config = config
        self.push_service = FCMNotification(self.config.fcm_key)

    async def do_push(self, txn, bulletin_secret, logger):
        logger.error(bulletin_secret)
        mongo = self.config.mongo

        if txn.get('relationship') and txn.get('dh_public_key') and txn.get('requester_rid') == rid:
            #friend request
            #if rid is the requester_rid, then we send a friend request notification to the requested_rid
            res = await mongo.async_site_db.fcmtokens.find({"rid": txn['requested_rid']})
            for token in res:
                result = self.push_service.notify_single_device(
                    registration_id=token['token'],
                    message_title='%s sent you a friend request!' % username,
                    message_body="See the request and approve!",
                    extra_kwargs={'priority': 'high'}
                )

        elif txn.get('relationship') and txn.get('dh_public_key') and txn.get('requested_rid') == rid:
            #friend accept
            #if rid is the requested_rid, then we send a friend accepted notification to the requester_rid
            res = await mongo.async_mongo.site_db.fcmtokens.find({"rid": txn['requester_rid']})
            for token in res:
                result = self.push_service.notify_single_device(
                    registration_id=token['token'],
                    message_title='%s approved your friend request!' % username,
                    message_body='Say "hi" to your friend!',
                    extra_kwargs={'priority': 'high'}
                )

        elif txn.get('relationship') and not txn.get('dh_public_key') and not txn.get('rid'):
            #post
            #we find all mutual friends of rid and send new post notifications to them
            rids = []
            rids.extend([x['requested_rid'] for x in self.config.BU.get_sent_friend_requests(rid)])
            rids.extend([x['requester_rid'] for x in self.config.BU.get_friend_requests(rid)])
            for friend_rid in rids:
                res = await mongo.async_mongo.site_db.fcmtokens.find({"rid": friend_rid})
                used_tokens = []
                for token in res:
                    if token['token'] in used_tokens:
                        continue
                    used_tokens.append(token['token'])

                    result = self.push_service.notify_single_device(
                        registration_id=token['token'],
                        message_title='%s has posted something!' % username,
                        message_body='Check out what your friend posted!',
                        extra_kwargs={'priority': 'high'}
                    )

        elif txn.get('relationship') and not txn.get('dh_public_key') and txn.get('rid'):
            #message
            #we find the relationship of the transaction rid and send a new message notification to the rid
            #of the relationship that does not match the arg rid
            my_bulletin_secret = self.config.bulletin_secret
            rids = sorted([str(my_bulletin_secret), str(bulletin_secret)], key=str.lower)
            rid = hashlib.sha256((str(rids[0]) + str(rids[1])).encode('utf-8')).digest().hex()
            logger.error(rid)
            rids = []
            txns = [x for x in self.config.GU.get_transactions_by_rid(txn['rid'], self.config.bulletin_secret, rid=True, raw=True)]
            rids.extend([x['requested_rid'] for x in txns if 'requested_rid' in x and rid != x['requested_rid']])
            rids.extend([x['requester_rid'] for x in txns if 'requester_rid' in x and rid != x['requester_rid']])
            logger.error(rids)
            username_txns = [x for x in self.config.GU.search_rid(rid)]
            username = ''
            for username_txn in username_txns:
                logger.error(username_txn['relationship']['their_username'])
                if username_txn['rid'] == rid:
                    username = username_txn['relationship']['their_username']
            for friend_rid in rids:
                res = mongo.site_db.fcmtokens.find({"rid": friend_rid})
                used_tokens = []
                for token in res:
                    if token['token'] in used_tokens:
                        continue
                    used_tokens.append(token['token'])

                    result = self.push_service.notify_single_device(
                        registration_id=token['token'],
                        message_title='New message from %s!' % username,
                        message_body='Go see what %s said!' % username,
                        extra_kwargs={'priority': 'high'}
                    )
                    print(result)
