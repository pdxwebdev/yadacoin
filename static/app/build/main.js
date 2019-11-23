webpackJsonp([0],{

/***/ 109:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return OpenGraphParserService; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__angular_http__ = __webpack_require__(18);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};


var OpenGraphParserService = /** @class */ (function () {
    function OpenGraphParserService(ahttp) {
        this.ahttp = ahttp;
        this.html = null;
        this.attrs = null;
        this.attrs = {
            "title": "title",
            "document.title": "title",
            "description": "description",
            "twitter:title": "title",
            "twitter:image": "image",
            "twitter:description": "description",
            "og:title": "title",
            "og:image": "image",
            "og:image:url": "image",
            "og:description": "description"
        };
    }
    OpenGraphParserService.prototype.parseFromUrl = function (url) {
        var _this = this;
        var output = { url: url };
        this.html = '';
        return new Promise(function (resolve, reject) {
            if (_this.isURL(url)) {
                _this.ahttp.get(url)
                    .subscribe(function (res) {
                    _this.html = res['_body'];
                    if (_this.isYouTubeURL(url)) {
                        var YTID = _this.getYouTubeID(url);
                        output['image'] = 'https://img.youtube.com/vi/' + YTID + '/0.jpg';
                    }
                    for (var key in _this.attrs) {
                        var attr = _this.getAttr(key);
                        if (attr) {
                            var escape = document.createElement('textarea');
                            escape.innerHTML = attr;
                            output[_this.attrs[key]] = escape.textContent;
                        }
                    }
                    resolve(output);
                });
            }
            else {
                resolve(false);
            }
        });
    };
    OpenGraphParserService.prototype.isURL = function (str) {
        var pattern = new RegExp('^(https?:\\/\\/)' + // protocol
            '((([a-z\\d]([a-z\\d-]*[a-z\\d])*)\\.?)+[a-z]{2,}|' + // domain name
            '((\\d{1,3}\\.){3}\\d{1,3}))' + // OR ip (v4) address
            '(\\:\\d+)?(\\/[-a-z\\d%_.~+]*)*' + // port and path
            '(\\?[;&a-z\\d%_.~+=-]*)?' + // query string
            '(\\#[-a-z\\d_]*)?$', 'i'); // fragment locator
        return pattern.test(str);
    };
    OpenGraphParserService.prototype.getYouTubeID = function (url) {
        var regExp = /^.*((youtu.be\/)|(v\/)|(\/u\/\w\/)|(embed\/)|(watch\?))\??v?=?([^#\&\?]*).*/;
        var match = url.match(regExp);
        return (match && match[7].length == 11) ? match[7] : false;
    };
    OpenGraphParserService.prototype.isYouTubeURL = function (str) {
        return str.indexOf('youtube.com') > -1 || str.indexOf('youtu.be') > -1 || str.indexOf('youtube-nocookie.com') > -1 ? true : false;
    };
    OpenGraphParserService.prototype.getAttr = function (attr) {
        var attrLocation = this.html.indexOf(attr);
        var beginningToAttr = this.html.substr(0, attrLocation);
        if (attr === 'title' || attr === 'description') {
            var tagBodyWithRemainder = this.html.substr(attrLocation + attr.length + 1);
            var closingTagStart = tagBodyWithRemainder.indexOf('</' + attr);
            var content = tagBodyWithRemainder.substr(0, closingTagStart);
            return content;
        }
        else {
            var reversed = beginningToAttr.split('').reverse().join('');
            var find = 'atem<';
            var tagStart = reversed.indexOf(find);
            var tagWithRemainder = this.html.substr(beginningToAttr.length - tagStart - 5);
            var tagEnd = tagWithRemainder.indexOf('>');
            var tag = tagWithRemainder.substr(0, tagEnd + 1);
            var contentAttrStart = tag.indexOf('content');
            if (contentAttrStart < 0) {
                contentAttrStart = tag.indexOf('value');
            }
            var contentAttrSub = tag.substr(contentAttrStart);
            var contentAttrStartQuote = contentAttrSub.indexOf('"');
            var contentWithRemainder = contentAttrSub.substr(contentAttrStartQuote + 1);
            var contentEnd = contentWithRemainder.indexOf('"');
            content = contentWithRemainder.substr(0, contentEnd);
            return content;
        }
    };
    OpenGraphParserService = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["B" /* Injectable */])(),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1__angular_http__["b" /* Http */]])
    ], OpenGraphParserService);
    return OpenGraphParserService;
}());

//# sourceMappingURL=opengraphparser.service.js.map

/***/ }),

/***/ 16:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return SettingsService; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};

var SettingsService = /** @class */ (function () {
    function SettingsService() {
        this.remoteSettings = {};
        this.remoteSettingsUrl = null;
        this.seeds = [];
        this.tokens = {};
        this.tokens = {};
    }
    SettingsService.prototype.go = function () {
        return new Promise(function (resolve, reject) {
        });
    };
    SettingsService = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["B" /* Injectable */])(),
        __metadata("design:paramtypes", [])
    ], SettingsService);
    return SettingsService;
}());

//# sourceMappingURL=settings.service.js.map

/***/ }),

/***/ 180:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return HomePage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__angular_forms__ = __webpack_require__(27);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2_ionic_angular__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__ionic_storage__ = __webpack_require__(33);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_bulletinSecret_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_graph_service__ = __webpack_require__(40);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__app_transaction_service__ = __webpack_require__(34);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__app_peer_service__ = __webpack_require__(181);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__list_list__ = __webpack_require__(51);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_10__profile_profile__ = __webpack_require__(86);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_11__postmodal__ = __webpack_require__(302);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_12__app_opengraphparser_service__ = __webpack_require__(109);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_13__ionic_native_social_sharing__ = __webpack_require__(85);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_14__app_settings_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_15__app_firebase_service__ = __webpack_require__(185);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_16__angular_http__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_17__app_autocomplete_provider__ = __webpack_require__(304);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};




















var HomePage = /** @class */ (function () {
    function HomePage(navCtrl, navParams, modalCtrl, storage, bulletinSecretService, alertCtrl, walletService, graphService, transactionService, openGraphParserService, socialSharing, settingsService, loadingCtrl, ahttp, firebaseService, events, toastCtrl, peerService, completeTestService) {
        var _this = this;
        this.navCtrl = navCtrl;
        this.navParams = navParams;
        this.modalCtrl = modalCtrl;
        this.storage = storage;
        this.bulletinSecretService = bulletinSecretService;
        this.alertCtrl = alertCtrl;
        this.walletService = walletService;
        this.graphService = graphService;
        this.transactionService = transactionService;
        this.openGraphParserService = openGraphParserService;
        this.socialSharing = socialSharing;
        this.settingsService = settingsService;
        this.loadingCtrl = loadingCtrl;
        this.ahttp = ahttp;
        this.firebaseService = firebaseService;
        this.events = events;
        this.toastCtrl = toastCtrl;
        this.peerService = peerService;
        this.completeTestService = completeTestService;
        this.postText = null;
        this.createdCode = null;
        this.scannedCode = null;
        this.key = null;
        this.blockchainAddress = null;
        this.balance = null;
        this.items = [];
        this.loading = false;
        this.loadingBalance = true;
        this.loadingModal = null;
        this.loadingModal2 = null;
        this.phrase = null;
        this.color = null;
        this.isCordova = null;
        this.toggled = {};
        this.reacts = {};
        this.comments = {};
        this.commentInputs = {};
        this.ids_to_get = [];
        this.comment_ids_to_get = [];
        this.commentReacts = {};
        this.myForm = new __WEBPACK_IMPORTED_MODULE_1__angular_forms__["b" /* FormGroup */]({
            searchTerm: new __WEBPACK_IMPORTED_MODULE_1__angular_forms__["a" /* FormControl */]('', [__WEBPACK_IMPORTED_MODULE_1__angular_forms__["g" /* Validators */].required])
        });
        this.location = window.location;
        this.prefix = 'usernames-';
        this.refresh(null)
            .then(function () {
            return _this.graphService.getInfo();
        })
            .then(function () {
            return new Promise(function (resolve, reject) {
                var options = new __WEBPACK_IMPORTED_MODULE_16__angular_http__["d" /* RequestOptions */]({ withCredentials: true });
                _this.ahttp.post(_this.settingsService.remoteSettings['baseUrl'] + '/fcm-token?origin=' + window.location.origin, {
                    rid: _this.graphService.graph.rid,
                }, options).subscribe(function () {
                    resolve();
                });
            });
        })
            .then(function () {
            if (!document.URL.startsWith('http') || document.URL.startsWith('http://localhost:8080')) {
                return _this.firebaseService.initFirebase();
            }
            else {
                // Initialize Firebase
                var config = {
                    apiKey: "AIzaSyAcJWjePVMBkEF8A3M-7oY_lT0MMXRDrpA",
                    authDomain: "yadacoin-bcaae.firebaseapp.com",
                    databaseURL: "https://yadacoin-bcaae.firebaseio.com",
                    projectId: "yadacoin-bcaae",
                    storageBucket: "yadacoin-bcaae.appspot.com",
                    messagingSenderId: "805178314562"
                };
                try {
                    firebase.initializeApp(config);
                    var messaging = firebase.messaging();
                    messaging.usePublicVapidKey('BLuv1UWDqzAyTtK5xlNaY4tFOz6vKbjuutTQ0KmBRG5btvVbydsrMTA-UeyMqY4oCC1Gu3sDwLfsg-iWtAg6IB0');
                    messaging.requestPermission().then(function () {
                        console.log('Notification permission granted.');
                        // TODO(developer): Retrieve an Instance ID token for use with FCM.
                        // ...
                    }).catch(function (err) {
                        console.log('Unable to get permission to notify.', err);
                    });
                    return messaging.getToken().then(function (currentToken) {
                        if (currentToken) {
                            _this.sendTokenToServer(currentToken);
                            _this.updateUIForPushEnabled(currentToken);
                        }
                        else {
                            // Show permission request.
                            console.log('No Instance ID token available. Request permission to generate one.');
                            // Show permission UI.
                            _this.updateUIForPushPermissionRequired();
                        }
                    }).catch(function (err) {
                        console.log('An error occurred while retrieving token. ', err);
                    });
                }
                catch (err) {
                }
            }
        });
    }
    ;
    HomePage.prototype.go = function () {
        var _this = this;
        return this.peerService.go()
            .then(function () {
            return _this.refresh(null);
        });
    };
    HomePage.prototype.submit = function () {
        if (!this.myForm.valid)
            return false;
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_10__profile_profile__["a" /* ProfilePage */], { item: this.myForm.value.searchTerm });
        console.log(this.myForm.value.searchTerm);
    };
    HomePage.prototype.sendTokenToServer = function (token) {
        var _this = this;
        return new Promise(function (resolve, reject) {
            var headers = new __WEBPACK_IMPORTED_MODULE_16__angular_http__["a" /* Headers */]({ 'Content-Type': 'application/json' });
            var options = new __WEBPACK_IMPORTED_MODULE_16__angular_http__["d" /* RequestOptions */]({ headers: headers, withCredentials: true });
            _this.ahttp.post(_this.settingsService.remoteSettings['baseUrl'] + '/fcm-token?origin=' + window.location.origin, {
                rid: _this.graphService.graph.rid,
                token: token,
            }, options).subscribe(function () {
                resolve();
            });
        });
    };
    HomePage.prototype.updateUIForPushEnabled = function (token) {
    };
    HomePage.prototype.updateUIForPushPermissionRequired = function () {
    };
    HomePage.prototype.react = function (e, item) {
        var _this = this;
        this.toggled[item.id] = false;
        return this.walletService.get()
            .then(function () {
            return _this.transactionService.generateTransaction({
                relationship: {
                    'react': e.char,
                    'id': item.id,
                    'bulletin_secret': _this.bulletinSecretService.bulletin_secret
                }
            });
        })
            .then(function () {
            return _this.transactionService.getFastGraphSignature();
        })
            .then(function (hash) {
            return _this.transactionService.sendTransaction();
        })
            .then(function () {
            var toast = _this.toastCtrl.create({
                message: 'React sent',
                duration: 2000
            });
            return toast.present();
        })
            .then(function () {
            _this.graphService.getReacts([item.id]);
        })
            .catch(function (err) {
            var toast = _this.toastCtrl.create({
                message: 'Something went wrong with your react!',
                duration: 2000
            });
            toast.present();
        });
    };
    HomePage.prototype.comment = function (item) {
        var _this = this;
        if (!this.commentInputs[item.id]) {
            alert('Comment cannot be empty.');
            return;
        }
        return this.walletService.get()
            .then(function () {
            return _this.transactionService.generateTransaction({
                relationship: {
                    'comment': _this.commentInputs[item.id],
                    'id': item.id,
                    'bulletin_secret': _this.bulletinSecretService.bulletin_secret
                }
            });
        })
            .then(function () {
            return _this.transactionService.getFastGraphSignature();
        })
            .then(function (hash) {
            return _this.transactionService.sendTransaction();
        })
            .then(function () {
            var toast = _this.toastCtrl.create({
                message: 'Comment posted',
                duration: 2000
            });
            return toast.present();
        })
            .then(function () {
            _this.graphService.getComments(_this.ids_to_get);
        })
            .then(function () {
            _this.commentInputs[item.id] = '';
        })
            .catch(function (err) {
            var toast = _this.toastCtrl.create({
                message: 'Something went wrong with your comment!',
                duration: 2000
            });
            toast.present();
        });
    };
    HomePage.prototype.commentReact = function (e, item) {
        var _this = this;
        this.toggled[item.id] = false;
        return this.walletService.get()
            .then(function () {
            return _this.transactionService.generateTransaction({
                relationship: {
                    'react': e.char,
                    'id': item.id,
                    'bulletin_secret': _this.bulletinSecretService.bulletin_secret
                }
            });
        })
            .then(function () {
            return _this.transactionService.getFastGraphSignature();
        })
            .then(function (hash) {
            return _this.transactionService.sendTransaction();
        })
            .then(function () {
            var toast = _this.toastCtrl.create({
                message: 'Comment react sent',
                duration: 2000
            });
            return toast.present();
        })
            .then(function () {
            for (var i = 0; i < Object.keys(_this.graphService.graph.comments).length; i++) {
                for (var j = 0; j < _this.graphService.graph.comments[Object.keys(_this.graphService.graph.comments)[i]].length; j++) {
                    _this.comment_ids_to_get.push(_this.graphService.graph.comments[Object.keys(_this.graphService.graph.comments)[i]][j].id);
                }
            }
            return _this.graphService.getCommentReacts(_this.comment_ids_to_get);
        })
            .then(function () {
            _this.graphService.getCommentReacts(_this.comment_ids_to_get);
        })
            .catch(function (err) {
            var toast = _this.toastCtrl.create({
                message: 'Something went wrong with your react!',
                duration: 2000
            });
            toast.present();
        });
    };
    HomePage.prototype.commentReplies = function (item) {
        var _this = this;
        if (!this.commentInputs[item.id]) {
            alert('Comment cannot be empty.');
            return;
        }
        return this.walletService.get()
            .then(function () {
            return _this.transactionService.generateTransaction({
                relationship: {
                    'comment': _this.commentInputs[item.id],
                    'id': item.id,
                    'bulletin_secret': _this.bulletinSecretService.bulletin_secret
                }
            });
        })
            .then(function () {
            return _this.transactionService.getFastGraphSignature();
        })
            .then(function (hash) {
            return _this.transactionService.sendTransaction();
        })
            .then(function () {
            var toast = _this.toastCtrl.create({
                message: 'Comment posted',
                duration: 2000
            });
            return toast.present();
        })
            .then(function () {
            for (var i = 0; i < Object.keys(_this.graphService.graph.comments).length; i++) {
                for (var j = 0; j < _this.graphService.graph.comments[Object.keys(_this.graphService.graph.comments)[i]].length; j++) {
                    _this.comment_ids_to_get.push(_this.graphService.graph.comments[Object.keys(_this.graphService.graph.comments)[i]][j].id);
                }
            }
            return _this.graphService.getCommentReacts(_this.comment_ids_to_get);
        })
            .then(function () {
            _this.graphService.getCommentReplies(_this.comment_ids_to_get);
        })
            .catch(function (err) {
            var toast = _this.toastCtrl.create({
                message: 'Something went wrong with your comment!',
                duration: 2000
            });
            toast.present();
        });
    };
    HomePage.prototype.showChat = function () {
        var item = { pageTitle: { title: "Chat" } };
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_9__list_list__["a" /* ListPage */], item);
    };
    HomePage.prototype.showFriendRequests = function () {
        var item = { pageTitle: { title: "Friend Requests" } };
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_9__list_list__["a" /* ListPage */], item);
    };
    HomePage.prototype.reactsDetail = function (item) {
        var data = { pageTitle: { title: "Reacts Detail" }, detail: this.graphService.graph.reacts[item.id] };
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_9__list_list__["a" /* ListPage */], data);
    };
    HomePage.prototype.commentReactsDetail = function (item) {
        var data = { pageTitle: { title: "Comment Reacts Detail" }, detail: this.graphService.graph.commentReacts[item.id] };
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_9__list_list__["a" /* ListPage */], data);
    };
    HomePage.prototype.refresh = function (refresher) {
        this.loading = true;
        this.loadingBalance = true;
        // this.loadingModal = this.loadingCtrl.create({
        //     content: 'Please wait...'
        // });
        // this.loadingModal.present();
        // this.storage.get('blockchainAddress').then((blockchainAddress) => {
        //     this.blockchainAddress = blockchainAddress;
        // });
        //put ourselves in the faucet
        /*
        this.ahttp.get(
            this.settingsService.remoteSettings['baseUrl'] + '/faucet?address=' + this.bulletinSecretService.key.getAddress()
        )
        .subscribe(()=>{}, () => {});
        */
        this.color = this.graphService.friend_request_count > 0 ? 'danger' : '';
        this.friendRequestColor = this.graphService.friend_request_count > 0 ? 'danger' : '';
        this.chatColor = this.graphService.new_messages_count > 0 ? 'danger' : '';
        this.signInColor = this.graphService.new_sign_ins_count > 0 ? 'danger' : '';
        //update our wallet
        /*
        return this.walletService.get()
        .then(() => {
            this.balance = this.walletService.wallet.balance;
            this.txnId = '';
            for(var i=0; i < this.walletService.wallet.txns_for_fastgraph.length; i++) {
                var txn = this.walletService.wallet.txns_for_fastgraph[i];
                if ((txn.signatures) && txn.rid == this.graphService.graph.rid) {
                    this.txnId = txn.id; // will always select the wrong txn id
                }
            }
            this.loadingBalance = false;;
            let headers = new Headers();
            headers.append('Authorization', 'Bearer ' + this.settingsService.tokens[this.bulletinSecretService.keyname]);
            let options = new RequestOptions({ headers: headers, withCredentials: true });
            this.ahttp.get(this.settingsService.remoteSettings['baseUrl'] + '/unlocked?rid=' + this.graphService.graph.rid + '&id=' + '' + '&bulletin_secret=' + this.bulletinSecretService.bulletin_secret + '&origin=' + window.location.origin, options).subscribe((res) => {
                var data = JSON.parse(res['_body']);
                this.signedIn = data.authenticated;
            });
        })
        .then(() => {
            return this.graphService.getFriends()
        })
        .then(() => {
            return this.graphService.getNewMessages()
        })
        .then(() => {
            return this.graphService.getNewSignIns();
        })
        .then(() => {
            return this.graphService.getNewGroupMessages();
        })
        .then(() => {
            return this.generateFeed();
        })
        .then(() => {
            return this.graphService.getReacts(this.ids_to_get);
        })
        .then(() => {
            return this.graphService.getComments(this.ids_to_get);
        })
        .then(() => {
            for (var i=0; i < Object.keys(this.graphService.graph.comments).length; i++) {
                for (var j=0; j < this.graphService.graph.comments[Object.keys(this.graphService.graph.comments)[i]].length; j++) {
                    this.comment_ids_to_get.push(this.graphService.graph.comments[Object.keys(this.graphService.graph.comments)[i]][j].id);
                }
            }
            return this.graphService.getCommentReacts(this.comment_ids_to_get);
        })
        .then(() => {
            return this.graphService.getCommentReplies(this.comment_ids_to_get);
        })
        .then(() => {
            this.loading = false;
            this.loadingModal.dismiss().catch(() => {});
            if(refresher) refresher.complete();
            this.chatColor = this.graphService.new_messages_count > 0 ? 'danger' : '';
            this.chatColor = this.graphService.new_sign_ins_count > 0 ? 'danger' : '';
        })
        .catch(() => {
            this.loading = false;
            this.loadingModal.dismiss().catch(() => {});
        });
        */
        this.loading = false;
        //    this.loadingModal.dismiss().catch(() => {});
        return new Promise(function (resolve, reject) {
            return resolve();
        });
    };
    HomePage.prototype.search = function () {
        var _this = this;
        return this.ahttp.get(this.settingsService.remoteSettings['baseUrl'] + '/search?searchTerm=' + this.searchTerm)
            .subscribe(function (res) {
            _this.searchResults = res.json();
        }, function () { });
    };
    HomePage.prototype.generateFeed = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            ////////////////////////////////////////////
            // all friend post operations
            ////////////////////////////////////////////
            var graphArray = _this.graphService.graph.posts;
            if (graphArray.length == 0) {
                _this.loading = false;
                _this.loadingModal.dismiss().catch(function () { });
            }
            graphArray.sort(function (a, b) {
                if (parseInt(a.time) < parseInt(b.time))
                    return 1;
                if (parseInt(a.time) > parseInt(b.time))
                    return -1;
                return 0;
            });
            _this.ids_to_get = [];
            _this.items = [];
            var _loop_1 = function (i) {
                _this.ids_to_get.push(graphArray[i].id);
                if (_this.openGraphParserService.isURL(graphArray[i].relationship.postText)) {
                    if (!document.URL.startsWith('http') || document.URL.startsWith('http://localhost:8080')) {
                        _this.openGraphParserService.parseFromUrl(graphArray[i].relationship.postText).then(function (data) {
                            data['id'] = graphArray[i].id;
                            data['username'] = graphArray[i].username;
                            _this.items.push(data);
                            if ((graphArray.length - 1) == i) {
                                _this.loading = false;
                                _this.loadingModal.dismiss().catch(function () { });
                            }
                        });
                    }
                    else {
                        _this.openGraphParserService.parseFromUrl(_this.settingsService.remoteSettings['baseUrl'] + '/get-url?url=' + encodeURIComponent(graphArray[i].relationship.postText)).then(function (data) {
                            data['id'] = graphArray[i].id;
                            data['username'] = graphArray[i].username;
                            _this.items.push(data);
                            if ((graphArray.length - 1) == i) {
                                _this.loading = false;
                                _this.loadingModal.dismiss().catch(function () { });
                            }
                        });
                    }
                }
                else {
                    data = {
                        username: graphArray[i].username,
                        title: '',
                        description: graphArray[i].relationship.postText,
                        id: graphArray[i].id
                    };
                    if (graphArray[i].relationship.postFileName) {
                        data['fileName'] = graphArray[i].relationship.postFileName;
                        data['fileData'] = graphArray[i].relationship.postFile;
                    }
                    _this.items.push(data);
                    if ((graphArray.length - 1) == i) {
                        _this.loading = false;
                        _this.loadingModal.dismiss().catch(function () { });
                    }
                }
            };
            var data;
            for (var i = 0; i < graphArray.length; i++) {
                _loop_1(i);
            }
            resolve();
        });
    };
    HomePage.prototype.download = function (item) {
        this.ahttp.post(this.settingsService.remoteSettings['baseUrl'] + '/renter/loadasciidd', { 'asciisia': item.fileData })
            .subscribe(function (res) {
            alert('File can now be found in your sia files');
        }, function (err) {
            alert('File can now be found in your sia files');
        });
    };
    HomePage.prototype.register = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            _this.walletService.get().then(function () {
                _this.ahttp.get(_this.settingsService.remoteSettings['baseUrl'] + '/register')
                    .subscribe(function (res) {
                    var data = JSON.parse(res['_body']);
                    var raw_dh_private_key = window.crypto.getRandomValues(new Uint8Array(32));
                    var raw_dh_public_key = X25519.getPublic(raw_dh_private_key);
                    var dh_private_key = _this.toHex(raw_dh_private_key);
                    var dh_public_key = _this.toHex(raw_dh_public_key);
                    data.dh_private_key = dh_private_key;
                    data.dh_public_key = dh_public_key;
                    var hash = _this.getTransaction(data, resolve);
                    resolve(hash);
                });
            });
        }) // we cannot do fastgraph registrations. The signing process verifies a relationship. So one must already exist.
            .then(function (hash) {
            return _this.transactionService.sendTransaction();
        })
            .then(function () {
            return _this.transactionService.sendCallback();
        })
            .then(function () {
            _this.refresh(null);
        })
            .catch(function () {
            alert('error registering');
            _this.loadingModal.dismiss().catch(function () { });
        });
    };
    HomePage.prototype.getTransaction = function (info, resolve) {
        return this.transactionService.generateTransaction({
            relationship: {
                dh_private_key: info.dh_private_key,
                their_bulletin_secret: info.bulletin_secret,
                their_username: info.username,
                my_bulletin_secret: this.bulletinSecretService.bulletin_secret,
                my_username: this.bulletinSecretService.username
            },
            dh_public_key: info.dh_public_key,
            requested_rid: info.requested_rid,
            requester_rid: info.requester_rid,
            callbackurl: info.callbackurl,
            to: info.to,
            resolve: resolve
        });
    };
    HomePage.prototype.sharePhrase = function () {
        this.socialSharing.share(this.bulletinSecretService.username, "Add me on Yada Coin!");
    };
    HomePage.prototype.addFriend = function () {
        var _this = this;
        var buttons = [];
        buttons.push({
            text: 'Add',
            handler: function (data) {
                _this.pasteFriend(data.phrase);
            }
        });
        var alert = this.alertCtrl.create({
            inputs: [
                {
                    name: 'phrase',
                    placeholder: 'Type username here...'
                }
            ],
            buttons: buttons
        });
        alert.setTitle('Request Friend');
        alert.setSubTitle('How do you want to request this friend?');
        alert.present();
    };
    HomePage.prototype.createGroup = function () {
        var _this = this;
        this.graphService.getInfo()
            .then(function () {
            return new Promise(function (resolve, reject) {
                var alert = _this.alertCtrl.create({
                    title: 'Set group name',
                    inputs: [
                        {
                            name: 'groupname',
                            placeholder: 'Group name'
                        }
                    ],
                    buttons: [
                        {
                            text: 'Save',
                            handler: function (data) {
                                var toast = _this.toastCtrl.create({
                                    message: 'Group created',
                                    duration: 2000
                                });
                                toast.present();
                                resolve(data.groupname);
                            }
                        }
                    ]
                });
                alert.present();
            });
        })
            .then(function (groupname) {
            return new Promise(function (resolve, reject) {
                if (!groupname)
                    return reject();
                var key = foobar.bitcoin.ECPair.makeRandom();
                var wif = key.toWIF();
                var pubKey = key.getPublicKeyBuffer().toString('hex');
                var address = key.getAddress();
                var bulletin_secret = foobar.base64.fromByteArray(key.sign(foobar.bitcoin.crypto.sha256(groupname)).toDER());
                var raw_dh_private_key = window.crypto.getRandomValues(new Uint8Array(32));
                var raw_dh_public_key = X25519.getPublic(raw_dh_private_key);
                var dh_private_key = _this.toHex(raw_dh_private_key);
                var dh_public_key = _this.toHex(raw_dh_public_key);
                resolve({
                    their_public_key: pubKey,
                    their_address: address,
                    their_bulletin_secret: bulletin_secret,
                    their_username: groupname,
                    wif: wif,
                    dh_public_key: dh_public_key,
                    dh_private_key: dh_private_key
                });
            });
        })
            .then(function (info) {
            var bulletin_secrets = [_this.graphService.graph.bulletin_secret, info.their_bulletin_secret].sort(function (a, b) {
                return a.toLowerCase().localeCompare(b.toLowerCase());
            });
            var requested_rid = forge.sha256.create().update(bulletin_secrets[0] + bulletin_secrets[1]).digest().toHex();
            return _this.transactionService.generateTransaction({
                relationship: {
                    dh_private_key: info.dh_private_key,
                    their_bulletin_secret: info.their_bulletin_secret,
                    their_public_key: info.their_public_key,
                    their_username: info.their_username,
                    their_address: info.their_address,
                    my_bulletin_secret: _this.bulletinSecretService.generate_bulletin_secret(),
                    my_username: _this.bulletinSecretService.username,
                    wif: info.wif,
                    group: true
                },
                dh_public_key: info.dh_public_key,
                to: info.their_address,
                requester_rid: _this.graphService.graph.rid,
                requested_rid: requested_rid
            });
        }).then(function (txn) {
            return _this.transactionService.sendTransaction();
        })
            .then(function (hash) {
            if (_this.settingsService.remoteSettings['walletUrl']) {
                return _this.graphService.getInfo();
            }
        })
            .then(function () {
            return _this.refresh(null);
        })
            .then(function () {
            _this.events.publish('pages-settings');
        })
            .catch(function (err) {
            console.log(err);
            _this.events.publish('pages');
        });
    };
    HomePage.prototype.joinGroup = function () {
        var _this = this;
        new Promise(function (resolve, reject) {
            var alert = _this.alertCtrl.create();
            alert.setTitle('Join');
            alert.setSubTitle('Copy and paste the entire string of characters from the invite');
            alert.addButton({
                text: 'Join',
                handler: function (data) {
                    var toast = _this.toastCtrl.create({
                        message: 'Group joined!',
                        duration: 2000
                    });
                    toast.present();
                    resolve(data.groupinvite);
                }
            });
            alert.addInput({
                type: 'text',
                placeholder: 'Past invite characters',
                name: 'groupinvite'
            });
            alert.present();
        })
            .then(function (groupinvite) {
            return new Promise(function (resolve, reject) {
                if (!groupinvite)
                    return reject();
                var invite = JSON.parse(Base64.decode(groupinvite));
                var raw_dh_private_key = window.crypto.getRandomValues(new Uint8Array(32));
                var raw_dh_public_key = X25519.getPublic(raw_dh_private_key);
                var dh_private_key = _this.toHex(raw_dh_private_key);
                var dh_public_key = _this.toHex(raw_dh_public_key);
                resolve({
                    their_address: invite.their_address,
                    their_public_key: invite.their_public_key,
                    their_bulletin_secret: invite.their_bulletin_secret,
                    their_username: invite.their_username,
                    dh_public_key: dh_public_key,
                    dh_private_key: dh_private_key,
                    requested_rid: invite.requested_rid
                });
            });
        })
            .then(function (info) {
            return _this.transactionService.generateTransaction({
                relationship: {
                    dh_private_key: info.dh_private_key,
                    my_bulletin_secret: _this.bulletinSecretService.generate_bulletin_secret(),
                    my_username: _this.bulletinSecretService.username,
                    their_address: info.their_address,
                    their_public_key: info.their_public_key,
                    their_bulletin_secret: info.their_bulletin_secret,
                    their_username: info.their_username,
                    group: true
                },
                requester_rid: info.requester_rid,
                requested_rid: info.requested_rid,
                dh_public_key: info.dh_public_key,
                to: info.their_address
            });
        }).then(function (txn) {
            return _this.transactionService.sendTransaction();
        })
            .then(function (hash) {
            if (_this.settingsService.remoteSettings['walletUrl']) {
                return _this.graphService.getInfo();
            }
        })
            .then(function () {
            return _this.refresh(null);
        })
            .then(function () {
            _this.events.publish('pages-settings');
        })
            .catch(function (err) {
            _this.events.publish('pages');
        });
    };
    HomePage.prototype.unlockWallet = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            var alert = _this.alertCtrl.create({
                title: 'Paste the private key or WIF of the server.',
                inputs: [
                    {
                        name: 'key_or_wif',
                        placeholder: 'Private key or WIF',
                        type: 'password'
                    }
                ],
                buttons: [
                    {
                        text: 'Cancel',
                        role: 'cancel',
                        handler: function (data) {
                            console.log('Cancel clicked');
                            reject();
                        }
                    },
                    {
                        text: 'Unlock',
                        handler: function (data) {
                            var options = new __WEBPACK_IMPORTED_MODULE_16__angular_http__["d" /* RequestOptions */]({ withCredentials: true });
                            _this.ahttp.post(_this.settingsService.remoteSettings['baseUrl'] + '/unlock?origin=' + encodeURIComponent(window.location.origin), { key_or_wif: data.key_or_wif }, options)
                                .subscribe(function (res) {
                                _this.settingsService.tokens[_this.bulletinSecretService.keyname] = res.json()['token'];
                                var toast = _this.toastCtrl.create({
                                    message: 'Wallet unlocked',
                                    duration: 2000
                                });
                                toast.present();
                                resolve(res);
                            }, function (err) {
                                reject(data.key_or_wif);
                            });
                        }
                    }
                ]
            });
            alert.present();
        }).catch(function () {
            console.log('canceled unlock');
        });
    };
    HomePage.prototype.pasteFriend = function (phrase) {
        var _this = this;
        //this.loadingModal2 = this.loadingCtrl.create({
        //    content: 'Please wait...'
        //});
        //this.loadingModal.present();
        this.ahttp.get(this.settingsService.remoteSettings['baseUrl'] + '/search?phrase=' + phrase + '&bulletin_secret=' + this.bulletinSecretService.bulletin_secret)
            .subscribe(function (res) {
            //this.loadingModal2.dismiss();
            _this.alertRoutine(JSON.parse(res['_body']));
        }, function (err) {
            //this.loadingModal2.dismiss();
            alert('Username not found.');
        });
    };
    HomePage.prototype.alertRoutine = function (info) {
        var _this = this;
        if (this.walletService.wallet.balance < 1.01) {
            var alert_1 = this.alertCtrl.create();
            alert_1.setTitle('Insuficient Funds');
            alert_1.setSubTitle('You need at least 1.01 YadaCoins');
            alert_1.addButton('OK');
            alert_1.present();
            return;
        }
        if (info.requester_rid && info.requested_rid && info.requester_rid === info.requested_rid) {
            var alert_2 = this.alertCtrl.create();
            alert_2.setTitle('Oops!');
            alert_2.setSubTitle('You are trying to request yourself. :)');
            alert_2.addButton({
                text: 'Cancel',
                handler: function (data) {
                    _this.loadingModal.dismiss().catch(function () { });
                }
            });
            alert_2.present();
            return;
        }
        var alert = this.alertCtrl.create();
        alert.setTitle('Approve Transaction');
        alert.setSubTitle('You are about to spend 1.01 coins (1 coin + 0.01 fee)');
        alert.addButton({
            text: 'Cancel',
            handler: function (data) {
                _this.loadingModal.dismiss().catch(function () { });
            }
        });
        alert.addButton({
            text: 'Confirm',
            handler: function (data) {
                // camera permission was granted
                var requester_rid = info.requester_rid;
                var requested_rid = info.requested_rid;
                if (requester_rid && requested_rid) {
                    // get rid from bulletin secrets
                }
                else {
                    requester_rid = '';
                    requested_rid = '';
                }
                //////////////////////////////////////////////////////////////////////////
                // create and send transaction to create the relationship on the blockchain
                //////////////////////////////////////////////////////////////////////////
                _this.walletService.get().then(function () {
                    var raw_dh_private_key = window.crypto.getRandomValues(new Uint8Array(32));
                    var raw_dh_public_key = X25519.getPublic(raw_dh_private_key);
                    var dh_private_key = _this.toHex(raw_dh_private_key);
                    var dh_public_key = _this.toHex(raw_dh_public_key);
                    info.dh_private_key = dh_private_key;
                    info.dh_public_key = dh_public_key;
                    return _this.transactionService.generateTransaction({
                        relationship: {
                            dh_private_key: info.dh_private_key,
                            their_bulletin_secret: info.bulletin_secret,
                            their_username: info.username,
                            my_bulletin_secret: _this.bulletinSecretService.generate_bulletin_secret(),
                            my_username: _this.bulletinSecretService.username
                        },
                        dh_public_key: info.dh_public_key,
                        requested_rid: info.requested_rid,
                        requester_rid: info.requester_rid,
                        to: info.to
                    });
                }).then(function (hash) {
                    return new Promise(function (resolve, reject) {
                        _this.ahttp.post(_this.settingsService.remoteSettings['baseUrl'] + '/sign-raw-transaction', {
                            hash: hash,
                            bulletin_secret: _this.bulletinSecretService.bulletin_secret,
                            input: _this.transactionService.transaction.inputs[0].id,
                            id: _this.transactionService.transaction.id,
                            txn: _this.transactionService.transaction
                        })
                            .subscribe(function (res) {
                            //this.loadingModal2.dismiss();
                            try {
                                var data_1 = res.json();
                                _this.transactionService.transaction.signatures = [data_1.signature];
                                resolve();
                            }
                            catch (err) {
                                reject();
                                _this.loadingModal.dismiss().catch(function () { });
                            }
                        }, function (err) {
                            //this.loadingModal2.dismiss();
                        });
                    });
                }).then(function (txn) {
                    return _this.transactionService.sendTransaction();
                }).then(function (txn) {
                    _this.loadingModal.dismiss().catch(function () { });
                    var alert = _this.alertCtrl.create();
                    alert.setTitle('Friend Request Sent');
                    alert.setSubTitle('Your Friend Request has been sent successfully.');
                    alert.addButton('Ok');
                    alert.present();
                }).catch(function (err) {
                    console.log(err);
                });
            }
        });
        alert.present();
    };
    HomePage.prototype.alertRoutineForMessage = function (info) {
        var _this = this;
        if (this.walletService.wallet.balance < 0.01) {
            var alert_3 = this.alertCtrl.create();
            alert_3.setTitle('Insuficient Funds');
            alert_3.setSubTitle('You need at least 1.01 YadaCoins');
            alert_3.addButton('OK');
            alert_3.present();
            return;
        }
        var alert = this.alertCtrl.create();
        alert.setTitle('Approve Transaction');
        alert.setSubTitle('You are about to spend 0.01 coins (0.01 fee)');
        alert.addButton({
            text: 'Cancel',
            handler: function (data) {
                _this.loadingModal.dismiss().catch(function () { });
            }
        });
        alert.addButton({
            text: 'Confirm',
            handler: function (data) {
                //////////////////////////////////////////////////////////////////////////
                // create and send transaction to create the relationship on the blockchain
                //////////////////////////////////////////////////////////////////////////
                _this.walletService.get().then(function (txn) {
                    return new Promise(function (resolve, reject) {
                        var hash = _this.transactionService.generateTransaction({
                            dh_public_key: info.dh_public_key,
                            dh_private_key: info.dh_private_key,
                            relationship: {
                                signIn: info.relationship.signIn
                            },
                            shared_secret: info.shared_secret,
                            resolve: resolve,
                            rid: info.rid
                        });
                        if (hash) {
                            resolve(hash);
                        }
                        else {
                            reject('could not generate hash');
                        }
                    });
                }).then(function (hash) {
                    return new Promise(function (resolve, reject) {
                        _this.ahttp.post(_this.settingsService.remoteSettings['baseUrl'] + '/sign-raw-transaction', {
                            hash: hash,
                            bulletin_secret: _this.bulletinSecretService.bulletin_secret,
                            input: _this.transactionService.transaction.inputs[0].id,
                            id: _this.transactionService.transaction.id,
                            txn: _this.transactionService.transaction
                        })
                            .subscribe(function (res) {
                            //this.loadingModal2.dismiss();
                            try {
                                var data_2 = res.json();
                                _this.transactionService.transaction.signatures = [data_2.signature];
                                resolve();
                            }
                            catch (err) {
                                reject();
                                _this.loadingModal.dismiss().catch(function () { });
                            }
                        }, function (err) {
                            //this.loadingModal2.dismiss();
                        });
                    });
                }).then(function () {
                    return _this.transactionService.sendTransaction();
                }).then(function () {
                    return _this.transactionService.sendCallback();
                }).then(function (txn) {
                    _this.loadingModal.dismiss().catch(function () { });
                    var alert = _this.alertCtrl.create();
                    alert.setTitle('Friend Request Sent');
                    alert.setSubTitle('Your Friend Request has been sent successfully.');
                    alert.addButton('Ok');
                    alert.present();
                }).catch(function (err) {
                    //alert('transaction error');
                    _this.loadingModal.dismiss().catch(function () { });
                });
            }
        });
        alert.present();
    };
    HomePage.prototype.signIn = function () {
        var _this = this;
        this.walletService.get().then(function (signin_code) {
            return _this.graphService.getSharedSecretForRid(_this.graphService.graph.rid);
        }).then(function (args) {
            return new Promise(function (resolve, reject) {
                var options = new __WEBPACK_IMPORTED_MODULE_16__angular_http__["d" /* RequestOptions */]({ withCredentials: true });
                _this.ahttp.get(_this.settingsService.remoteSettings['loginUrl'] + '?origin=' + window.location.origin, options)
                    .subscribe(function (res) {
                    try {
                        return _this.transactionService.generateTransaction({
                            dh_public_key: args['dh_public_key'],
                            dh_private_key: args['dh_private_key'],
                            relationship: {
                                signIn: JSON.parse(res['_body']).signin_code
                            },
                            shared_secret: args['shared_secret'],
                            rid: _this.graphService.graph.rid
                        }).then(function (hash) {
                            _this.txnId = _this.transactionService.transaction.id;
                            resolve(hash);
                        });
                    }
                    catch (err) {
                        reject();
                        _this.loadingModal.dismiss().catch(function () { });
                    }
                }, function (err) {
                });
            });
        }).then(function (hash) {
            return new Promise(function (resolve, reject) {
                _this.ahttp.post(_this.settingsService.remoteSettings['baseUrl'] + '/sign-raw-transaction', {
                    hash: hash,
                    bulletin_secret: _this.bulletinSecretService.bulletin_secret,
                    input: _this.transactionService.transaction.inputs[0].id,
                    id: _this.transactionService.transaction.id,
                    txn: _this.transactionService.transaction
                })
                    .subscribe(function (res) {
                    try {
                        var data = res.json();
                        _this.transactionService.transaction.signatures = [data.signature];
                        resolve();
                    }
                    catch (err) {
                        reject();
                    }
                }, function (err) {
                });
            });
        }).then(function () {
            return _this.transactionService.sendTransaction();
        }).then(function () {
            _this.signedIn = true;
            _this.refresh(null);
        }).catch(function (err) {
            alert(err);
        });
    };
    HomePage.prototype.itemTapped = function (event, item) {
        item.pageTitle = "Posts";
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_9__list_list__["a" /* ListPage */], {
            item: item
        });
    };
    HomePage.prototype.presentModal = function () {
        var modal = this.modalCtrl.create(__WEBPACK_IMPORTED_MODULE_11__postmodal__["a" /* PostModal */], { blockchainAddress: this.settingsService.remoteSettings['baseUrl'], logicalParent: this });
        modal.present();
    };
    HomePage.prototype.share = function (item) {
        var _this = this;
        this.walletService.get().then(function () {
            return new Promise(function (resolve, reject) {
                console.log(status);
                var alert = _this.alertCtrl.create();
                alert.setTitle('Approve Transaction');
                alert.setSubTitle('You are about to spend 0.01 coins ( 0.01 fee)');
                alert.addButton('Cancel');
                alert.addButton({
                    text: 'Confirm',
                    handler: function (data) {
                        // camera permission was granted
                        _this.transactionService.generateTransaction({
                            relationship: {
                                postText: item.url || item.description
                            },
                            resolve: resolve
                        });
                    }
                });
                alert.present();
            });
        });
    };
    HomePage.prototype.decrypt = function (message) {
        var key = forge.pkcs5.pbkdf2(forge.sha256.create().update(this.bulletinSecretService.key.toWIF()).digest().toHex(), 'salt', 400, 32);
        var decipher = forge.cipher.createDecipher('AES-CBC', key);
        var enc = this.hexToBytes(message);
        decipher.start({ iv: enc.slice(0, 16) });
        decipher.update(forge.util.createBuffer(enc.slice(16)));
        decipher.finish();
        return decipher.output;
    };
    HomePage.prototype.hexToBytes = function (s) {
        var arr = [];
        for (var i = 0; i < s.length; i += 2) {
            var c = s.substr(i, 2);
            arr.push(parseInt(c, 16));
        }
        return String.fromCharCode.apply(null, arr);
    };
    HomePage.prototype.toHex = function (byteArray) {
        var callback = function (byte) {
            return ('0' + (byte & 0xFF).toString(16)).slice(-2);
        };
        return Array.from(byteArray, callback).join('');
    };
    HomePage = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["n" /* Component */])({
            selector: 'page-home',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/home/home.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n  </ion-navbar>\n</ion-header>\n\n<ion-content padding>\n  <ion-spinner *ngIf="loading"></ion-spinner>\n  <ion-row>\n    <form [formGroup]="myForm" (ngSubmit)="submit()">\n      <ion-auto-complete [dataProvider]="completeTestService" formControlName="searchTerm" required></ion-auto-complete>\n      <button icon-left ion-button type="submit" block [disabled]="!myForm.valid">\n        <ion-icon name="eye"></ion-icon>\n        View profile\n      </button>\n    </form>\n    <ion-col col-lg-12 col-md-12 col-sm-12>\n      <button ion-button large secondary (click)="unlockWallet()" *ngIf="peerService.mode">\n        Unlock wallet&nbsp;<ion-icon name="create"></ion-icon>\n      </button>\n      <button ion-button large secondary (click)="createGroup()">\n        Create Group&nbsp;<ion-icon name="create"></ion-icon>\n      </button>\n    </ion-col>\n  </ion-row>\n  <ion-list col-lg-7>\n    <ion-item *ngFor="let item of items">\n      <ion-card>\n        <a href="{{item.url}}" *ngIf="item.url" height="400">\n          <img src="{{item.image}}" *ngIf="item.image">\n          <ion-card-content>\n            <ion-card-title style="text-overflow:ellipsis;" text-wrap>\n              {{item.title}}\n            </ion-card-title>\n            <h2>{{item.username}}</h2>\n            <p *ngIf="item.description" style="text-overflow:ellipsis;" text-wrap>\n              {{item.description}}\n            </p>\n          </ion-card-content>\n        </a>\n        <div *ngIf="!item.url">\n          <ion-card-content>\n            <ion-card-title style="text-overflow:ellipsis;" text-wrap>\n              {{item.title}}\n            </ion-card-title>\n            <h2>{{item.username}}</h2>\n            <h1 *ngIf="item.description" style="text-overflow:ellipsis;" text-wrap>\n              {{item.description}}\n            </h1>\n            <span *ngIf="item.fileName">Files:</span><br>\n            <a *ngIf="item.fileName" style="text-overflow:ellipsis; margin-top:50px;" text-wrap (click)="download(item)">\n              <strong>{{item.fileName}}</strong>\n            </a>\n          </ion-card-content>\n        </div>\n        <ion-row no-padding text-wrap (click)="reactsDetail(item)">\n            <ion-item><span *ngFor="let react of graphService.graph.reacts[item.id]" [innerHTML]="react.relationship.react"></span></ion-item>\n        </ion-row>\n        <ion-row no-padding>\n          <ion-col>\n            <button ion-button clear small icon-start (click)="toggled[item.id] = !toggled[item.id]" [(emojiPickerIf)]="toggled[item.id]" [emojiPickerDirection]="\'right\'" (emojiPickerSelect)="react($event, item)">\n              <ion-icon name=\'sunny\'></ion-icon>\n              React\n            </button>\n          </ion-col>\n          <ion-col text-right>\n            <button ion-button clear small color="danger" icon-start (click)="share(item)">\n              <ion-icon name=\'share-alt\'></ion-icon>\n              Share\n            </button>\n          </ion-col>\n          <ion-item>\n            <ion-input type="text" placeholder="Comment text..." [(ngModel)]="commentInputs[item.id]" (keyup.enter)="comment(item)">\n            </ion-input>\n          </ion-item>\n          <ion-col text-right>\n            <button ion-button clear small color="danger" icon-start (click)="comment(item)">\n              <ion-icon name=\'text\'></ion-icon>\n              Post comment\n            </button>\n          </ion-col>\n        </ion-row>\n        <ion-row>\n          <ion-list col-lg-7>\n            <ion-item *ngFor="let comment of graphService.graph.comments[item.id]">\n              <button style="z-index:1000;"ion-button clear small icon-start (click)="toggled[comment.id] = !toggled[comment.id]" [(emojiPickerIf)]="toggled[comment.id]" [emojiPickerDirection]="\'right\'" (emojiPickerSelect)="commentReact($event, comment)">\n                <ion-icon name=\'sunny\'></ion-icon>\n                React\n              </button>\n              <strong [innerHTML]="comment.username"></strong>\n              <ion-item [innerHTML]="comment.relationship.comment" text-wrap></ion-item>\n              <ion-row *ngIf="graphService.graph.commentReacts[comment.id] && graphService.graph.commentReacts[comment.id].length > 0" no-padding text-wrap (click)="commentReactsDetail(comment)">\n                  <ion-item><span *ngFor="let react of graphService.graph.commentReacts[comment.id]" [innerHTML]="react.relationship.react"></span></ion-item>\n              </ion-row>\n            </ion-item>\n          </ion-list>\n        </ion-row>\n      </ion-card>\n    </ion-item>\n  </ion-list>\n</ion-content>\n'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/home/home.html"*/
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_2_ionic_angular__["i" /* NavController */],
            __WEBPACK_IMPORTED_MODULE_2_ionic_angular__["j" /* NavParams */],
            __WEBPACK_IMPORTED_MODULE_2_ionic_angular__["g" /* ModalController */],
            __WEBPACK_IMPORTED_MODULE_3__ionic_storage__["b" /* Storage */],
            __WEBPACK_IMPORTED_MODULE_4__app_bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_2_ionic_angular__["a" /* AlertController */],
            __WEBPACK_IMPORTED_MODULE_5__app_wallet_service__["a" /* WalletService */],
            __WEBPACK_IMPORTED_MODULE_6__app_graph_service__["a" /* GraphService */],
            __WEBPACK_IMPORTED_MODULE_7__app_transaction_service__["a" /* TransactionService */],
            __WEBPACK_IMPORTED_MODULE_12__app_opengraphparser_service__["a" /* OpenGraphParserService */],
            __WEBPACK_IMPORTED_MODULE_13__ionic_native_social_sharing__["a" /* SocialSharing */],
            __WEBPACK_IMPORTED_MODULE_14__app_settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_2_ionic_angular__["f" /* LoadingController */],
            __WEBPACK_IMPORTED_MODULE_16__angular_http__["b" /* Http */],
            __WEBPACK_IMPORTED_MODULE_15__app_firebase_service__["a" /* FirebaseService */],
            __WEBPACK_IMPORTED_MODULE_2_ionic_angular__["b" /* Events */],
            __WEBPACK_IMPORTED_MODULE_2_ionic_angular__["l" /* ToastController */],
            __WEBPACK_IMPORTED_MODULE_8__app_peer_service__["a" /* PeerService */],
            __WEBPACK_IMPORTED_MODULE_17__app_autocomplete_provider__["a" /* CompleteTestService */]])
    ], HomePage);
    return HomePage;
}());

//# sourceMappingURL=home.js.map

/***/ }),

/***/ 181:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return PeerService; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__ionic_storage__ = __webpack_require__(33);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__angular_http__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3_rxjs_operators__ = __webpack_require__(55);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__bulletinSecret_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__transaction_service__ = __webpack_require__(34);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__settings_service__ = __webpack_require__(16);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};








var PeerService = /** @class */ (function () {
    function PeerService(ahttp, walletService, transactionService, bulletinSecretService, settingsService, storage) {
        this.ahttp = ahttp;
        this.walletService = walletService;
        this.transactionService = transactionService;
        this.bulletinSecretService = bulletinSecretService;
        this.settingsService = settingsService;
        this.storage = storage;
        this.seeds = null;
        this.loading = false;
        this.seeds = [
            //{"host": "0.0.0.0","port": 8001 },
            { "host": "34.237.46.10", "port": 80 },
        ];
        this.mode = false;
    }
    PeerService.prototype.go = function () {
        var _this = this;
        if (this.loading)
            return;
        this.loading = true;
        return this.storage.get('static-node')
            .then(function (node) {
            if (node) {
                _this.mode = true;
                return new Promise(function (resolve, reject) {
                    return resolve(node);
                });
            }
            else {
                return _this.storage.get('node');
            }
        })
            .then(function (node) {
            return new Promise(function (resolve, reject) {
                var seedPeer = '';
                if (node) {
                    _this.settingsService.remoteSettingsUrl = node;
                }
                else {
                    var min = 0;
                    var max = _this.seeds.length - 1;
                    var number = Math.floor(Math.random() * (+max - +min)) + +min;
                    if (!_this.seeds[number])
                        return reject(false);
                    seedPeer = 'http://' + _this.seeds[number]['host'] + ':' + _this.seeds[number]['port'];
                }
                return resolve(seedPeer);
            });
        })
            .then(function (seedPeer) {
            if (_this.settingsService.remoteSettingsUrl) {
                return _this.getConfig();
            }
            else {
                return _this.getPeers(seedPeer);
            }
        })
            .then(function (step) {
            if (step === 'config') {
                return _this.getConfig();
            }
            return new Promise(function (resolve, reject) {
                return resolve();
            });
        })
            .then(function () {
            return _this.walletService.get();
        })
            .then(function () {
            return _this.setupRelationship();
        })
            .catch(function (e) {
            _this.settingsService.remoteSettings = {};
            _this.settingsService.remoteSettingsUrl = null;
            _this.loading = false;
            console.log('faled getting peers' + e);
            _this.storage.remove(_this.mode ? 'static-node' : 'node');
            setTimeout(function () { return _this.go(); }, 1000);
        });
    };
    PeerService.prototype.getPeers = function (seedPeer) {
        var _this = this;
        return new Promise(function (resolve, reject) {
            _this.ahttp.get(seedPeer + '/get-peers').pipe(Object(__WEBPACK_IMPORTED_MODULE_3_rxjs_operators__["timeout"])(1000)).subscribe(function (res) {
                var peers = res.json().peers;
                var min = 0;
                var max = peers.length - 1;
                var number = Math.floor(Math.random() * (+max - +min)) + +min;
                if (!peers[number])
                    return reject(false);
                _this.settingsService.remoteSettingsUrl = 'http://' + peers[number]['host'] + ':' + peers[number]['port'];
                _this.storage.set('node', _this.settingsService.remoteSettingsUrl);
                resolve('config');
            }, function (err) {
                _this.loading = false;
                return reject(err);
            });
        });
    };
    PeerService.prototype.getConfig = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            _this.ahttp.get(_this.settingsService.remoteSettingsUrl + '/yada_config.json').pipe(Object(__WEBPACK_IMPORTED_MODULE_3_rxjs_operators__["timeout"])(1000)).subscribe(function (res) {
                _this.loading = false;
                _this.settingsService.remoteSettings = res.json();
                resolve();
            }, function (err) {
                _this.loading = false;
                return reject(err);
            });
        });
    };
    PeerService.prototype.setupRelationship = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            _this.ahttp.get(_this.settingsService.remoteSettings['baseUrl'] + '/register')
                .subscribe(function (res) {
                var data = JSON.parse(res['_body']);
                var raw_dh_private_key = window.crypto.getRandomValues(new Uint8Array(32));
                var raw_dh_public_key = X25519.getPublic(raw_dh_private_key);
                var dh_private_key = _this.toHex(raw_dh_private_key);
                var dh_public_key = _this.toHex(raw_dh_public_key);
                data.dh_private_key = dh_private_key;
                data.dh_public_key = dh_public_key;
                var hash = _this.transactionService.generateTransaction({
                    relationship: {
                        dh_private_key: data.dh_private_key,
                        their_bulletin_secret: data.bulletin_secret,
                        their_username: data.username,
                        my_bulletin_secret: _this.bulletinSecretService.bulletin_secret,
                        my_username: _this.bulletinSecretService.username
                    },
                    dh_public_key: data.dh_public_key,
                    requested_rid: data.requested_rid,
                    requester_rid: data.requester_rid,
                    callbackurl: data.callbackurl,
                    to: data.to,
                    resolve: resolve
                });
                resolve(hash);
            });
        }) // we cannot do fastgraph registrations. The signing process verifies a relationship. So one must already exist.
            .then(function (hash) {
            return _this.transactionService.sendTransaction();
        })
            .catch(function (err) {
            console.log(err);
        });
    };
    PeerService.prototype.hexToBytes = function (s) {
        var arr = [];
        for (var i = 0; i < s.length; i += 2) {
            var c = s.substr(i, 2);
            arr.push(parseInt(c, 16));
        }
        return String.fromCharCode.apply(null, arr);
    };
    PeerService.prototype.toHex = function (byteArray) {
        var callback = function (byte) {
            return ('0' + (byte & 0xFF).toString(16)).slice(-2);
        };
        return Array.from(byteArray, callback).join('');
    };
    PeerService = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["B" /* Injectable */])(),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_2__angular_http__["b" /* Http */],
            __WEBPACK_IMPORTED_MODULE_5__wallet_service__["a" /* WalletService */],
            __WEBPACK_IMPORTED_MODULE_6__transaction_service__["a" /* TransactionService */],
            __WEBPACK_IMPORTED_MODULE_4__bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_7__settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_1__ionic_storage__["b" /* Storage */]])
    ], PeerService);
    return PeerService;
}());

//# sourceMappingURL=peer.service.js.map

/***/ }),

/***/ 182:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return ChatPage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__ionic_storage__ = __webpack_require__(33);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_graph_service__ = __webpack_require__(40);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_bulletinSecret_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_transaction_service__ = __webpack_require__(34);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__app_settings_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__list_list__ = __webpack_require__(51);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__profile_profile__ = __webpack_require__(86);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_10__angular_http__ = __webpack_require__(18);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};












var ChatPage = /** @class */ (function () {
    function ChatPage(navCtrl, navParams, storage, walletService, transactionService, alertCtrl, graphService, loadingCtrl, bulletinSecretService, settingsService, ahttp, toastCtrl) {
        var _this = this;
        this.navCtrl = navCtrl;
        this.navParams = navParams;
        this.storage = storage;
        this.walletService = walletService;
        this.transactionService = transactionService;
        this.alertCtrl = alertCtrl;
        this.graphService = graphService;
        this.loadingCtrl = loadingCtrl;
        this.bulletinSecretService = bulletinSecretService;
        this.settingsService = settingsService;
        this.ahttp = ahttp;
        this.toastCtrl = toastCtrl;
        this.rid = navParams.data.item.transaction.rid;
        this.requester_rid = navParams.data.item.transaction.requester_rid || '';
        this.requested_rid = navParams.data.item.transaction.requested_rid || '';
        var key = 'last_message_height-' + navParams.data.item.transaction.rid;
        if (navParams.data.item.transaction.height)
            this.storage.set(key, navParams.data.item.transaction.time);
        this.storage.get('blockchainAddress').then(function (blockchainAddress) {
            _this.blockchainAddress = blockchainAddress;
        });
        this.public_key = this.bulletinSecretService.key.getPublicKeyBuffer().toString('hex');
        this.refresh(null, true);
    }
    ChatPage.prototype.parseChats = function () {
        if (this.graphService.graph.messages[this.rid]) {
            this.chats = this.graphService.graph.messages[this.rid];
            for (var i = 0; i < this.chats.length; i++) {
                this.chats[i].time = new Date(parseInt(this.chats[i].time)).toISOString().slice(0, 19).replace('T', ' ');
            }
        }
        else {
            this.chats = [];
        }
    };
    ChatPage.prototype.refresh = function (refresher, showLoading) {
        var _this = this;
        if (showLoading === void 0) { showLoading = true; }
        if (showLoading) {
            this.loading = true;
        }
        this.graphService.getMessages(this.rid)
            .then(function () {
            _this.loading = false;
            if (refresher)
                refresher.complete();
            return _this.parseChats();
        })
            .then(function () {
            setTimeout(function () { return _this.content.scrollToBottom(1000); }, 500);
        });
    };
    ChatPage.prototype.viewProfile = function (item) {
        var _this = this;
        return this.graphService.getFriends()
            .then(function () {
            for (var i = 0; i < _this.graphService.graph.friends.length; i++) {
                var friend = _this.graphService.graph.friends[i];
                if (friend.rid === item.rid) {
                    item = friend;
                }
            }
            _this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_9__profile_profile__["a" /* ProfilePage */], {
                item: item
            });
        });
    };
    ChatPage.prototype.joinGroup = function (item) {
        var _this = this;
        return new Promise(function (resolve, reject) {
            var invite = item.relationship.chatText;
            var raw_dh_private_key = window.crypto.getRandomValues(new Uint8Array(32));
            var raw_dh_public_key = X25519.getPublic(raw_dh_private_key);
            var dh_private_key = _this.toHex(raw_dh_private_key);
            var dh_public_key = _this.toHex(raw_dh_public_key);
            resolve({
                their_address: invite.their_address,
                their_public_key: invite.their_public_key,
                their_bulletin_secret: invite.their_bulletin_secret,
                their_username: invite.their_username,
                dh_public_key: dh_public_key,
                dh_private_key: dh_private_key,
                requested_rid: invite.requested_rid,
                requester_rid: _this.graphService.graph.rid
            });
        })
            .then(function (info) {
            return _this.transactionService.generateTransaction({
                relationship: {
                    dh_private_key: info.dh_private_key,
                    my_bulletin_secret: _this.bulletinSecretService.generate_bulletin_secret(),
                    my_username: _this.bulletinSecretService.username,
                    their_address: info.their_address,
                    their_public_key: info.their_public_key,
                    their_bulletin_secret: info.their_bulletin_secret,
                    their_username: info.their_username,
                    group: true
                },
                requester_rid: info.requester_rid,
                requested_rid: info.requested_rid,
                dh_public_key: info.dh_public_key,
                to: info.their_address
            });
        }).then(function (txn) {
            return _this.transactionService.sendTransaction();
        })
            .then(function (hash) {
            if (_this.settingsService.remoteSettings['walletUrl']) {
                return _this.graphService.getInfo();
            }
        })
            .then(function () {
            var toast = _this.toastCtrl.create({
                message: 'Group joined!',
                duration: 2000
            });
            toast.present();
            return _this.refresh(null);
        })
            .catch(function (err) {
        });
    };
    ChatPage.prototype.send = function () {
        var _this = this;
        var alert = this.alertCtrl.create();
        alert.setTitle('Approve transaction');
        alert.setSubTitle('You are about to spend 0.01 coins ( 0.01 fee)');
        alert.addButton('Cancel');
        alert.addButton({
            text: 'Confirm',
            handler: function (data) {
                _this.walletService.get()
                    .then(function () {
                    return _this.graphService.getFriends();
                })
                    .then(function () {
                    var dh_public_key = _this.graphService.keys[_this.rid].dh_public_keys[0];
                    var dh_private_key = _this.graphService.keys[_this.rid].dh_private_keys[0];
                    if (dh_public_key && dh_private_key) {
                        var privk = new Uint8Array(dh_private_key.match(/[\da-f]{2}/gi).map(function (h) {
                            return parseInt(h, 16);
                        }));
                        var pubk = new Uint8Array(dh_public_key.match(/[\da-f]{2}/gi).map(function (h) {
                            return parseInt(h, 16);
                        }));
                        var shared_secret = _this.toHex(X25519.getSharedKey(privk, pubk));
                        // camera permission was granted
                        return _this.transactionService.generateTransaction({
                            dh_public_key: dh_public_key,
                            dh_private_key: dh_private_key,
                            relationship: {
                                chatText: _this.chatText
                            },
                            shared_secret: shared_secret,
                            rid: _this.rid,
                            requester_rid: _this.requester_rid,
                            requested_rid: _this.requested_rid,
                        });
                    }
                    else {
                        return new Promise(function (resolve, reject) {
                            var alert = _this.alertCtrl.create();
                            alert.setTitle('Friendship not yet processed');
                            alert.setSubTitle('Please wait a few minutes and try again');
                            alert.addButton('Ok');
                            alert.present();
                            return reject();
                        });
                    }
                }).then(function (txn) {
                    return _this.transactionService.sendTransaction();
                }).then(function () {
                    _this.chatText = '';
                    _this.refresh(null);
                })
                    .catch(function (err) {
                    console.log(err);
                    var alert = _this.alertCtrl.create();
                    alert.setTitle('Message error');
                    alert.setSubTitle(err);
                    alert.addButton('Ok');
                    alert.present();
                });
            }
        });
        alert.present();
    };
    ChatPage.prototype.showChat = function () {
        var item = { pageTitle: { title: "Chat" } };
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_8__list_list__["a" /* ListPage */], item);
    };
    ChatPage.prototype.showFriendRequests = function () {
        var item = { pageTitle: { title: "Friend Requests" } };
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_8__list_list__["a" /* ListPage */], item);
    };
    ChatPage.prototype.toHex = function (byteArray) {
        var callback = function (byte) {
            return ('0' + (byte & 0xFF).toString(16)).slice(-2);
        };
        return Array.from(byteArray, callback).join('');
    };
    ChatPage = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["n" /* Component */])({
            selector: 'page-chat',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/chat/chat.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n  </ion-navbar>\n</ion-header>\n<ion-content #content>\n  <ion-refresher (ionRefresh)="refresh($event)">\n    <ion-refresher-content></ion-refresher-content>\n  </ion-refresher>\n  <ion-spinner *ngIf="loading"></ion-spinner>\n	<ion-list>\n	  <ion-item *ngFor="let item of chats" text-wrap>\n        <strong><span ion-text style="font-size: 20px;" (click)="viewProfile(item)">{{(item.public_key == public_key) ? graphService.friends_indexed[item.rid].relationship.my_username : graphService.friends_indexed[item.rid].relationship.their_username}}</span> </strong><span style="font-size: 10px; color: rgb(88, 88, 88);" ion-text>{{item.time}}</span>\n        <h3 *ngIf="!item.relationship.isInvite">{{item.relationship.chatText}}</h3>\n        <h3 *ngIf="item.relationship.isInvite && item.relationship.chatText.group === true">Invite to join {{item.relationship.chatText.their_username}}</h3>\n        <button *ngIf="item.relationship.isInvite && item.relationship.chatText.group === true" ion-button (click)="joinGroup(item)">Join group</button>\n        <button *ngIf="item.relationship.isInvite && item.relationship.chatText.group !== true" ion-button (click)="requestFriend(item)">Join group</button>\n        <hr />\n	  </ion-item>\n	</ion-list>\n</ion-content>\n<ion-footer>\n  <ion-item>\n    <ion-label floating>Chat text</ion-label>\n    <ion-input [(ngModel)]="chatText" (keyup.enter)="send()"></ion-input>\n  </ion-item>\n  <button ion-button (click)="send()">Send</button>\n</ion-footer>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/chat/chat.html"*/,
            queries: {
                content: new __WEBPACK_IMPORTED_MODULE_0__angular_core__["_14" /* ViewChild */]('content')
            }
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["i" /* NavController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["j" /* NavParams */],
            __WEBPACK_IMPORTED_MODULE_2__ionic_storage__["b" /* Storage */],
            __WEBPACK_IMPORTED_MODULE_5__app_wallet_service__["a" /* WalletService */],
            __WEBPACK_IMPORTED_MODULE_6__app_transaction_service__["a" /* TransactionService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["a" /* AlertController */],
            __WEBPACK_IMPORTED_MODULE_3__app_graph_service__["a" /* GraphService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["f" /* LoadingController */],
            __WEBPACK_IMPORTED_MODULE_4__app_bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_7__app_settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_10__angular_http__["b" /* Http */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["l" /* ToastController */]])
    ], ChatPage);
    return ChatPage;
}());

//# sourceMappingURL=chat.js.map

/***/ }),

/***/ 183:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return GroupPage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__ionic_storage__ = __webpack_require__(33);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_graph_service__ = __webpack_require__(40);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_bulletinSecret_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_transaction_service__ = __webpack_require__(34);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__app_settings_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__list_list__ = __webpack_require__(51);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__profile_profile__ = __webpack_require__(86);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_10__siafiles_siafiles__ = __webpack_require__(184);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_11__angular_http__ = __webpack_require__(18);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};













var GroupPage = /** @class */ (function () {
    function GroupPage(navCtrl, navParams, storage, walletService, transactionService, alertCtrl, graphService, loadingCtrl, bulletinSecretService, settingsService, ahttp, modalCtrl, toastCtrl) {
        var _this = this;
        this.navCtrl = navCtrl;
        this.navParams = navParams;
        this.storage = storage;
        this.walletService = walletService;
        this.transactionService = transactionService;
        this.alertCtrl = alertCtrl;
        this.graphService = graphService;
        this.loadingCtrl = loadingCtrl;
        this.bulletinSecretService = bulletinSecretService;
        this.settingsService = settingsService;
        this.ahttp = ahttp;
        this.modalCtrl = modalCtrl;
        this.toastCtrl = toastCtrl;
        this.extraInfo = {};
        this.wallet_mode = true;
        this.item = navParams.data.item.transaction;
        this.rid = navParams.data.item.transaction.rid;
        this.requester_rid = navParams.data.item.transaction.requester_rid;
        this.requested_rid = navParams.data.item.transaction.requested_rid;
        this.their_address = navParams.data.item.transaction.relationship.their_address;
        this.their_public_key = navParams.data.item.transaction.relationship.their_public_key;
        this.their_bulletin_secret = navParams.data.item.transaction.relationship.their_bulletin_secret;
        this.their_username = navParams.data.item.transaction.relationship.their_username;
        var key = 'last_message_height-' + navParams.data.item.transaction.rid;
        if (navParams.data.item.transaction.height)
            this.storage.set(key, navParams.data.item.transaction.time);
        this.storage.get('blockchainAddress').then(function (blockchainAddress) {
            _this.blockchainAddress = blockchainAddress;
        });
        this.refresh(null, true);
    }
    GroupPage.prototype.showInvite = function () {
        var _this = this;
        this.graphService.getFriends()
            .then(function () {
            var alert = _this.alertCtrl.create();
            alert.setTitle('Invite');
            alert.setSubTitle('Select a friend to invite.');
            alert.addButton({
                text: 'Confirm',
                handler: function (data) {
                    _this.walletService.get()
                        .then(function () {
                        var dh_public_key = _this.graphService.keys[data.rid].dh_public_keys[0];
                        var dh_private_key = _this.graphService.keys[data.rid].dh_private_keys[0];
                        if (dh_public_key && dh_private_key) {
                            var privk = new Uint8Array(dh_private_key.match(/[\da-f]{2}/gi).map(function (h) {
                                return parseInt(h, 16);
                            }));
                            var pubk = new Uint8Array(dh_public_key.match(/[\da-f]{2}/gi).map(function (h) {
                                return parseInt(h, 16);
                            }));
                            var shared_secret = _this.toHex(X25519.getSharedKey(privk, pubk));
                        }
                        var myAddress = _this.bulletinSecretService.key.getAddress();
                        var to = false;
                        for (var h = 0; h < data.outputs.length; h++) {
                            if (data.outputs[h].to != myAddress) {
                                to = data.outputs[h].to;
                            }
                        }
                        return _this.transactionService.generateTransaction({
                            relationship: {
                                chatText: Base64.encode(JSON.stringify({
                                    their_public_key: _this.item.public_key,
                                    their_bulletin_secret: _this.item.relationship.their_bulletin_secret,
                                    their_username: _this.item.relationship.their_username,
                                    their_address: _this.item.relationship.their_address,
                                    group: true,
                                    requested_rid: _this.requested_rid
                                }))
                            },
                            rid: data.rid,
                            requester_rid: data.requester_rid,
                            requested_rid: data.requested_rid,
                            shared_secret: shared_secret,
                            to: to
                        });
                    }).then(function (txn) {
                        return _this.transactionService.sendTransaction();
                    }).then(function () {
                        var toast = _this.toastCtrl.create({
                            message: "Group invite sent!",
                            duration: 2000,
                        });
                        toast.present();
                        _this.groupChatText = '';
                        _this.refresh(null);
                    })
                        .catch(function (err) {
                        console.log(err);
                        var alert = _this.alertCtrl.create();
                        alert.setTitle('Message error');
                        alert.setSubTitle(err);
                        alert.addButton('Ok');
                        alert.present();
                    });
                }
            });
            for (var i = 0; i < _this.graphService.graph.friends.length; i++) {
                var friend = _this.graphService.graph.friends[i];
                alert.addInput({
                    name: 'username',
                    type: 'radio',
                    label: friend.relationship.their_username,
                    value: friend,
                    checked: false
                });
            }
            alert.present();
        });
    };
    GroupPage.prototype.parseChats = function () {
        var rid_to_use = this.requested_rid || this.rid;
        if (this.graphService.graph.messages[rid_to_use]) {
            this.chats = this.graphService.graph.messages[rid_to_use];
            for (var i = 0; i < this.chats.length; i++) {
                this.chats[i].time = new Date(parseInt(this.chats[i].time) * 1000).toISOString().slice(0, 19).replace('T', ' ');
            }
        }
        else {
            this.chats = [];
        }
    };
    GroupPage.prototype.refresh = function (refresher, showLoading) {
        var _this = this;
        if (showLoading === void 0) { showLoading = true; }
        if (showLoading) {
            this.loading = true;
        }
        this.graphService.getGroupMessages(this.their_bulletin_secret, this.requested_rid, this.rid)
            .then(function () {
            _this.loading = false;
            if (refresher)
                refresher.complete();
            return _this.parseChats();
        })
            .then(function () {
            setTimeout(function () { return _this.content.scrollToBottom(1000); }, 500);
        })
            .then(function () {
            return _this.getSiaFiles();
        })
            .catch(function (err) {
            console.log(err);
        });
    };
    GroupPage.prototype.presentModal = function () {
        var modal = this.modalCtrl.create(__WEBPACK_IMPORTED_MODULE_10__siafiles_siafiles__["a" /* SiaFiles */], {
            mode: 'modal',
            logicalParent: this,
            group: {
                their_bulletin_secret: this.their_bulletin_secret,
                rid: this.rid,
                requester_rid: this.requester_rid,
                requested_rid: this.requested_rid
            }
        });
        modal.present();
    };
    GroupPage.prototype.import = function (relationship) {
        return this.ahttp.post(this.settingsService.remoteSettings['baseUrl'] + '/sia-share-file?origin=' + encodeURIComponent(window.location.origin), relationship)
            .subscribe(function (res) {
            var files = res.json();
        });
    };
    GroupPage.prototype.getSiaFiles = function () {
        return this.ahttp.get(this.settingsService.remoteSettings['baseUrl'] + '/sia-files')
            .subscribe(function (res) {
            var files = res.json();
        });
    };
    GroupPage.prototype.toggleExtraInfo = function (pending) {
        var toast = this.toastCtrl.create({
            message: pending ? "Not yet saved on the blockchain" : "Saved on the blockchain",
            duration: 2000,
            cssClass: pending ? 'redToast' : 'greenToast',
            position: 'top'
        });
        toast.present();
    };
    GroupPage.prototype.viewProfile = function (item) {
        var _this = this;
        var bulletin_secrets = [this.bulletinSecretService.bulletin_secret, item.relationship.my_bulletin_secret].sort(function (a, b) {
            return a.toLowerCase().localeCompare(b.toLowerCase());
        });
        if (bulletin_secrets[0] === bulletin_secrets[1])
            return;
        return this.graphService.getFriends()
            .then(function () {
            var rid = foobar.bitcoin.crypto.sha256(bulletin_secrets[0] + bulletin_secrets[1]).toString('hex');
            for (var i = 0; i < _this.graphService.graph.friends.length; i++) {
                var friend = _this.graphService.graph.friends[i];
                if (friend.rid === rid) {
                    item = friend;
                }
            }
            _this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_9__profile_profile__["a" /* ProfilePage */], {
                item: item
            });
        });
    };
    GroupPage.prototype.send = function () {
        var _this = this;
        var alert = this.alertCtrl.create();
        alert.setTitle('Approve transaction');
        alert.setSubTitle('You are about to spend 0.00 coins ( 0.00 fee). Everything is free for now.');
        alert.addButton('Cancel');
        alert.addButton({
            text: 'Confirm',
            handler: function (data) {
                _this.walletService.get()
                    .then(function () {
                    return _this.graphService.getFriends();
                })
                    .then(function () {
                    return _this.transactionService.generateTransaction({
                        relationship: {
                            groupChatText: _this.groupChatText,
                            my_bulletin_secret: _this.bulletinSecretService.generate_bulletin_secret(),
                            my_username: _this.bulletinSecretService.username
                        },
                        their_bulletin_secret: _this.their_bulletin_secret,
                        rid: _this.rid,
                        requester_rid: _this.requester_rid,
                        requested_rid: _this.requested_rid
                    });
                }).then(function (hash) {
                    return new Promise(function (resolve, reject) {
                        if (_this.wallet_mode) {
                            return resolve();
                        }
                        _this.ahttp.post(_this.settingsService.remoteSettings['baseUrl'] + '/sign-raw-transaction', {
                            hash: hash,
                            bulletin_secret: _this.bulletinSecretService.bulletin_secret,
                            input: _this.transactionService.transaction.inputs[0].id,
                            id: _this.transactionService.transaction.id,
                            txn: _this.transactionService.transaction
                        })
                            .subscribe(function (res) {
                            //this.loadingModal2.dismiss();
                            try {
                                var data_1 = res.json();
                                _this.transactionService.transaction.signatures = [data_1.signature];
                                return resolve();
                            }
                            catch (err) {
                                return reject(err);
                                //this.loadingModal.dismiss().catch(() => {});
                            }
                        }, function (err) {
                            return reject(err);
                        });
                    });
                }).then(function (txn) {
                    return _this.transactionService.sendTransaction();
                }).then(function () {
                    _this.groupChatText = '';
                    _this.refresh(null);
                })
                    .catch(function (err) {
                    console.log(err);
                    var alert = _this.alertCtrl.create();
                    alert.setTitle('Message error');
                    alert.setSubTitle(err);
                    alert.addButton('Ok');
                    alert.present();
                });
            }
        });
        alert.present();
    };
    GroupPage.prototype.showChat = function () {
        var item = { pageTitle: { title: "Chat" } };
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_8__list_list__["a" /* ListPage */], item);
    };
    GroupPage.prototype.showFriendRequests = function () {
        var item = { pageTitle: { title: "Friend Requests" } };
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_8__list_list__["a" /* ListPage */], item);
    };
    GroupPage.prototype.toHex = function (byteArray) {
        var callback = function (byte) {
            return ('0' + (byte & 0xFF).toString(16)).slice(-2);
        };
        return Array.from(byteArray, callback).join('');
    };
    GroupPage.prototype.hexToBytes = function (s) {
        var arr = [];
        for (var i = 0; i < s.length; i += 2) {
            var c = s.substr(i, 2);
            arr.push(parseInt(c, 16));
        }
        return String.fromCharCode.apply(null, arr);
    };
    GroupPage = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["n" /* Component */])({
            selector: 'page-group',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/group/group.html"*/'<ion-header>\n    <ion-navbar>\n      <button ion-button menuToggle color="{{color}}">\n        <ion-icon name="menu"></ion-icon>\n      </button>\n      <button ion-button color="{{chatColor}}" title="Create invite" (click)="showInvite()">\n        Invite&nbsp;<ion-icon name="contacts"></ion-icon>\n      </button>\n    </ion-navbar>\n  </ion-header>\n  <ion-content #content>\n    <ion-refresher (ionRefresh)="refresh($event)">\n      <ion-refresher-content></ion-refresher-content>\n    </ion-refresher>\n    <ion-spinner *ngIf="loading"></ion-spinner>\n      <ion-list>\n        <ion-item *ngFor="let item of chats" text-wrap (click)="toggleExtraInfo(item.pending)">\n          <strong><span ion-text style="font-size: 20px;" (click)="viewProfile(item)">{{item.relationship.my_username || \'Anonymous\'}}</span> </strong><span style="font-size: 10px; color: rgb(88, 88, 88);" ion-text>{{item.time}}</span>\n          <h3 *ngIf="!item.relationship.groupChatFileName">{{item.relationship.groupChatText}}</h3>\n          <h3 *ngIf="item.relationship.groupChatFileName" (click)="receive(item.relationship)">{{item.relationship.groupChatFileName}}</h3>\n          <button *ngIf="item.relationship.groupChatFileName" ion-button (click)="import(item.relationship)">Import</button>\n          <ion-note color="primary">{{item.fee}} YADA</ion-note>\n          <ion-note *ngIf="item.pending" color="danger">Pending</ion-note>\n          <ion-note *ngIf="!item.pending" color="secondary">Saved</ion-note>\n          <hr />\n        </ion-item>\n      </ion-list>\n  </ion-content>\n  <ion-footer>\n    <ion-item>\n      <ion-label floating>Group text</ion-label>\n      <ion-input [(ngModel)]="groupChatText" (keyup.enter)="send()"></ion-input>\n    </ion-item>\n    <button ion-button (click)="send()">Send</button>\n    <button ion-button (click)="presentModal()">Share file</button>\n  </ion-footer>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/group/group.html"*/,
            queries: {
                content: new __WEBPACK_IMPORTED_MODULE_0__angular_core__["_14" /* ViewChild */]('content')
            }
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["i" /* NavController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["j" /* NavParams */],
            __WEBPACK_IMPORTED_MODULE_2__ionic_storage__["b" /* Storage */],
            __WEBPACK_IMPORTED_MODULE_5__app_wallet_service__["a" /* WalletService */],
            __WEBPACK_IMPORTED_MODULE_6__app_transaction_service__["a" /* TransactionService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["a" /* AlertController */],
            __WEBPACK_IMPORTED_MODULE_3__app_graph_service__["a" /* GraphService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["f" /* LoadingController */],
            __WEBPACK_IMPORTED_MODULE_4__app_bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_7__app_settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_11__angular_http__["b" /* Http */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["g" /* ModalController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["l" /* ToastController */]])
    ], GroupPage);
    return GroupPage;
}());

//# sourceMappingURL=group.js.map

/***/ }),

/***/ 184:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return SiaFiles; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__app_wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_transaction_service__ = __webpack_require__(34);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_opengraphparser_service__ = __webpack_require__(109);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_settings_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_bulletinSecret_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__angular_http__ = __webpack_require__(18);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};









var SiaFiles = /** @class */ (function () {
    function SiaFiles(navParams, viewCtrl, walletService, alertCtrl, transactionService, openGraphParserService, settingsService, bulletinSecretService, ahttp) {
        var _this = this;
        this.navParams = navParams;
        this.viewCtrl = viewCtrl;
        this.walletService = walletService;
        this.alertCtrl = alertCtrl;
        this.transactionService = transactionService;
        this.openGraphParserService = openGraphParserService;
        this.settingsService = settingsService;
        this.bulletinSecretService = bulletinSecretService;
        this.ahttp = ahttp;
        this.logicalParent = null;
        this.mode = '';
        this.postText = null;
        this.post = {};
        this.files = null;
        this.selectedFile = null;
        this.filepath = '';
        this.group = null;
        this.error = '';
        this.group = navParams.data.group;
        this.mode = navParams.data.mode || 'page';
        this.logicalParent = navParams.data.logicalParent;
        var headers = new __WEBPACK_IMPORTED_MODULE_7__angular_http__["a" /* Headers */]();
        headers.append('Authorization', 'Bearer ' + this.settingsService.tokens[this.bulletinSecretService.keyname]);
        var options = new __WEBPACK_IMPORTED_MODULE_7__angular_http__["d" /* RequestOptions */]({ headers: headers });
        this.ahttp.get(this.settingsService.remoteSettings['baseUrl'] + '/sia-files', options)
            .subscribe(function (res) {
            _this.files = res.json()['files'];
        }, function (err) {
            _this.error = err.json().message;
        });
    }
    SiaFiles.prototype.changeListener = function ($event) {
        this.filepath = $event.target.files[0];
    };
    SiaFiles.prototype.upload = function () {
        var _this = this;
        this.ahttp.get(this.settingsService.remoteSettings['baseUrl'] + '/sia-upload?filepath=' + encodeURIComponent(this.filepath))
            .subscribe(function (res) {
            _this.files = res.json()['files'];
        });
    };
    SiaFiles.prototype.delete = function (siapath) {
        var _this = this;
        this.ahttp.get(this.settingsService.remoteSettings['baseUrl'] + '/sia-delete?siapath=' + encodeURIComponent(siapath))
            .subscribe(function (res) {
            _this.files = res.json()['files'];
        });
    };
    SiaFiles.prototype.submit = function () {
        var _this = this;
        this.walletService.get().then(function () {
            return new Promise(function (resolve, reject) {
                if (_this.selectedFile) {
                    _this.ahttp.get(_this.settingsService.remoteSettings['baseUrl'] + '/sia-share-file?siapath=' + _this.selectedFile)
                        .subscribe(function (res) {
                        var sharefiledata = res.json()['filedata'];
                        _this.approveTxn(sharefiledata, resolve);
                    });
                }
                else {
                    _this.approveTxn(null, resolve);
                }
                console.log(status);
            }).then(function () {
                _this.dismiss();
            });
        });
    };
    SiaFiles.prototype.approveTxn = function (sharefiledata, resolve) {
        var _this = this;
        var alert = this.alertCtrl.create();
        alert.setTitle('Approve Transaction');
        alert.setSubTitle('You are about to spend 0.01 coins ( 0.01 fee)');
        alert.addButton('Cancel');
        alert.addButton({
            text: 'Confirm',
            handler: function (data) {
                // camera permission was granted
                new Promise(function (resolve, reject) {
                    if (sharefiledata) {
                        return _this.transactionService.generateTransaction({
                            relationship: {
                                groupChatText: _this.postText,
                                groupChatFile: sharefiledata,
                                groupChatFileName: _this.selectedFile,
                                my_bulletin_secret: _this.bulletinSecretService.generate_bulletin_secret(),
                                my_username: _this.bulletinSecretService.username
                            },
                            their_bulletin_secret: _this.group.their_bulletin_secret,
                            rid: _this.group.rid,
                            requester_rid: _this.group.requester_rid,
                            requested_rid: _this.group.requested_rid
                        })
                            .then(function () {
                            resolve();
                        })
                            .catch(function (err) {
                            reject();
                        });
                    }
                    else {
                        return _this.transactionService.generateTransaction({
                            relationship: {
                                postText: _this.postText
                            }
                        })
                            .then(function () {
                            resolve();
                        })
                            .catch(function (err) {
                            reject();
                        });
                    }
                })
                    .then(function (hash) {
                    return _this.transactionService.sendTransaction();
                })
                    .then(function () {
                    _this.dismiss();
                })
                    .catch(function (err) {
                    console.log('could not generate hash');
                });
            }
        });
        alert.present();
    };
    SiaFiles.prototype.dismiss = function () {
        this.logicalParent.refresh();
        this.viewCtrl.dismiss();
    };
    SiaFiles = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["n" /* Component */])({
            selector: 'modal-files',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/siafiles/siafiles.html"*/'<ion-header>\n  <ion-toolbar>\n    <ion-title>\n      Files\n    </ion-title>\n    <ion-buttons start *ngIf="mode == \'modal\'">\n      <button ion-button (click)="dismiss()">\n        <span ion-text color="primary" showWhen="ios">Cancel</span>\n        <ion-icon name="md-close" showWhen="android,windows,core"></ion-icon>\n      </button>\n    </ion-buttons>\n  </ion-toolbar>\n</ion-header>\n<ion-content>\n  <ion-item *ngIf="mode == \'modal\' && !error">\n    <ion-label>Files</ion-label>\n    <ion-select [(ngModel)]="selectedFile">\n      <ion-option *ngFor="let file of files" value="{{file.siapath}}">{{file.siapath}}</ion-option>\n    </ion-select>\n  </ion-item>\n  <ion-item *ngIf="!error">\n    <ion-textarea placeholder="Shortened url (35 chars max)" [(ngModel)]="filepath"></ion-textarea>\n  </ion-item>\n  <button ion-button secondary (click)="upload()" *ngIf="mode == \'page\' && !error" [disabled]="filepath">Upload</button>\n  <ion-item *ngIf="mode == \'page\' && !error">\n    <ion-list>\n      <ion-item *ngFor="let file of files">\n        <a *ngIf="file.available" href="{{file.stream_url}}" target="_blank">\n          <h3>{{file.siapath}}</h3>\n        </a>\n        <h3 *ngIf="!file.available">{{file.siapath}} (uploading...)</h3><button ion-button danger (click)="delete(file.siapath)">Delete</button>\n      </ion-item>\n    </ion-list>\n  </ion-item>\n  <button ion-button secondary (click)="submit()" *ngIf="mode == \'modal\'">Post</button>\n  <ion-card *ngIf="post.title">\n    <img src="{{post.image}}" *ngIf="post.image" />\n    <ion-card-content>\n      <ion-card-title>\n        {{post.title}}\n      </ion-card-title>\n      <p *ngIf="post.description">\n        {{post.description}}\n      </p>\n    </ion-card-content>\n  </ion-card>\n  <ion-item *ngIf="error">You must download the <a href="https://github.com/pdxwebdev/yadacoin/releases/latest" target="_blank">full node</a> to store and share files.</ion-item>\n</ion-content>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/siafiles/siafiles.html"*/
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["j" /* NavParams */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["m" /* ViewController */],
            __WEBPACK_IMPORTED_MODULE_2__app_wallet_service__["a" /* WalletService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["a" /* AlertController */],
            __WEBPACK_IMPORTED_MODULE_3__app_transaction_service__["a" /* TransactionService */],
            __WEBPACK_IMPORTED_MODULE_4__app_opengraphparser_service__["a" /* OpenGraphParserService */],
            __WEBPACK_IMPORTED_MODULE_5__app_settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_6__app_bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_7__angular_http__["b" /* Http */]])
    ], SiaFiles);
    return SiaFiles;
}());

//# sourceMappingURL=siafiles.js.map

/***/ }),

/***/ 185:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return FirebaseService; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__ionic_native_firebase__ = __webpack_require__(303);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__graph_service__ = __webpack_require__(40);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__settings_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__angular_http__ = __webpack_require__(18);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};





var FirebaseService = /** @class */ (function () {
    function FirebaseService(settingsService, graphService, firebase, ahttp) {
        this.settingsService = settingsService;
        this.graphService = graphService;
        this.firebase = firebase;
        this.ahttp = ahttp;
    }
    FirebaseService.prototype.initFirebase = function () {
        var _this = this;
        if (!document.URL.startsWith('http') || document.URL.startsWith('http://localhost:8080')) {
            this.firebase.getToken()
                .then(function (token) {
                console.log(token);
                _this.ahttp.post(_this.settingsService.remoteSettings['baseUrl'] + '/fcm-token', {
                    rid: _this.graphService.graph.rid,
                    token: token,
                }).subscribe(function () { });
            })
                .catch(function (error) {
                console.log('Error getting token', error);
            });
            this.firebase.onTokenRefresh()
                .subscribe(function (token) {
                console.log(token);
                _this.ahttp.post(_this.settingsService.remoteSettings['baseUrl'] + '/fcm-token', {
                    rid: _this.graphService.graph.rid,
                    token: token
                }).subscribe(function () { });
            });
            this.firebase.onNotificationOpen().subscribe(function (notification) {
                console.log(notification);
            });
        }
    };
    FirebaseService = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["B" /* Injectable */])(),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_3__settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_2__graph_service__["a" /* GraphService */],
            __WEBPACK_IMPORTED_MODULE_1__ionic_native_firebase__["a" /* Firebase */],
            __WEBPACK_IMPORTED_MODULE_4__angular_http__["b" /* Http */]])
    ], FirebaseService);
    return FirebaseService;
}());

//# sourceMappingURL=firebase.service.js.map

/***/ }),

/***/ 20:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return BulletinSecretService; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__ionic_storage__ = __webpack_require__(33);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2_ionic_angular__ = __webpack_require__(10);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};



var BulletinSecretService = /** @class */ (function () {
    function BulletinSecretService(storage, events) {
        this.storage = storage;
        this.events = events;
        this.key = null;
        this.bulletin_secret = null;
        this.keyname = null;
        this.keykeys = null;
        this.username = null;
    }
    BulletinSecretService.prototype.shared_encrypt = function (shared_secret, message) {
        var key = forge.pkcs5.pbkdf2(forge.sha256.create().update(shared_secret).digest().toHex(), 'salt', 400, 32);
        var cipher = forge.cipher.createCipher('AES-CBC', key);
        var iv = '';
        cipher.start({ iv: iv });
        cipher.update(forge.util.createBuffer(iv + message));
        cipher.finish();
        return cipher.output.toHex();
    };
    BulletinSecretService.prototype.get = function () {
        var _this = this;
        return this.all()
            .then(function (keys) {
            return _this.setKeyName(keys);
        })
            .then(function () {
            return _this.setKey();
        });
    };
    BulletinSecretService.prototype.setKeyName = function (keys) {
        var _this = this;
        return new Promise(function (resolve, reject) {
            keys.sort(function (a, b) {
                if (a.idx < b.idx)
                    return -1;
                if (a.idx > b.idx)
                    return 1;
                return 0;
            });
            if (!_this.keyname) {
                _this.storage.get('last-keyname').then(function (key) {
                    if (key && typeof key == 'string') {
                        _this.keyname = key;
                    }
                    else {
                        _this.keyname = keys[0].idx;
                    }
                    resolve(keys);
                });
            }
            else {
                resolve(keys);
            }
        });
    };
    BulletinSecretService.prototype.setKey = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            _this.storage.get(_this.keyname).then(function (key) {
                _this.key = foobar.bitcoin.ECPair.fromWIF(key);
                _this.username = _this.keyname.substr('usernames-'.length);
                _this.bulletin_secret = _this.generate_bulletin_secret();
                return resolve();
            });
        });
    };
    BulletinSecretService.prototype.generate_bulletin_secret = function () {
        return foobar.base64.fromByteArray(this.key.sign(foobar.bitcoin.crypto.sha256(this.username)).toDER());
    };
    BulletinSecretService.prototype.set = function (key) {
        var _this = this;
        return new Promise(function (resolve, reject) {
            _this.keyname = key;
            return _this.storage.set('last-keyname', key)
                .then(function () {
                return _this.storage.remove('usernames-');
            })
                .then(function (key) {
                return _this.get();
            })
                .then(function () {
                return _this.setKey();
            })
                .then(function () {
                return resolve();
            })
                .catch(function () {
                return reject();
            });
        });
    };
    BulletinSecretService.prototype.create = function (username) {
        var _this = this;
        return new Promise(function (resolve, reject) {
            if (!username)
                return reject();
            _this.keyname = 'usernames-' + username;
            _this.storage.set('last-keyname', _this.keyname);
            _this.username = username;
            _this.key = foobar.bitcoin.ECPair.makeRandom();
            _this.storage.set(_this.keyname, _this.key.toWIF());
            _this.bulletin_secret = _this.generate_bulletin_secret();
            return _this.get().then(function () {
                return resolve();
            });
        });
    };
    BulletinSecretService.prototype.import = function (keyWif, username) {
        var _this = this;
        return new Promise(function (resolve, reject) {
            if (!username)
                return reject();
            _this.keyname = 'usernames-' + username;
            _this.storage.set('last-keyname', _this.keyname);
            _this.username = username;
            _this.storage.set(_this.keyname, keyWif.trim());
            _this.key = foobar.bitcoin.ECPair.fromWIF(keyWif.trim());
            _this.bulletin_secret = _this.generate_bulletin_secret();
            return _this.get().then(function () {
                return resolve();
            });
        });
    };
    BulletinSecretService.prototype.all = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            var keykeys = [];
            _this.storage.forEach(function (value, key) {
                if (key.substr(0, 'usernames-'.length) === 'usernames-') {
                    keykeys.push({ key: value, idx: key });
                }
            })
                .then(function () {
                _this.keykeys = keykeys;
                resolve(keykeys);
            });
        });
    };
    BulletinSecretService.prototype.decrypt = function (message) {
        var key = forge.pkcs5.pbkdf2(forge.sha256.create().update(this.key.toWIF()).digest().toHex(), 'salt', 400, 32);
        var decipher = forge.cipher.createDecipher('AES-CBC', key);
        var enc = this.hexToBytes(message);
        decipher.start({ iv: enc.slice(0, 16) });
        decipher.update(forge.util.createBuffer(enc.slice(16)));
        decipher.finish();
        return decipher.output;
    };
    BulletinSecretService.prototype.hexToBytes = function (s) {
        var arr = [];
        for (var i = 0; i < s.length; i += 2) {
            var c = s.substr(i, 2);
            arr.push(parseInt(c, 16));
        }
        return String.fromCharCode.apply(null, arr);
    };
    BulletinSecretService = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["B" /* Injectable */])(),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1__ionic_storage__["b" /* Storage */],
            __WEBPACK_IMPORTED_MODULE_2_ionic_angular__["b" /* Events */]])
    ], BulletinSecretService);
    return BulletinSecretService;
}());

//# sourceMappingURL=bulletinSecret.service.js.map

/***/ }),

/***/ 217:
/***/ (function(module, exports) {

function webpackEmptyAsyncContext(req) {
	// Here Promise.resolve().then() is used instead of new Promise() to prevent
	// uncatched exception popping up in devtools
	return Promise.resolve().then(function() {
		throw new Error("Cannot find module '" + req + "'.");
	});
}
webpackEmptyAsyncContext.keys = function() { return []; };
webpackEmptyAsyncContext.resolve = webpackEmptyAsyncContext;
module.exports = webpackEmptyAsyncContext;
webpackEmptyAsyncContext.id = 217;

/***/ }),

/***/ 25:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return WalletService; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__bulletinSecret_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__settings_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__angular_http__ = __webpack_require__(18);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};




var WalletService = /** @class */ (function () {
    function WalletService(ahttp, bulletinSecretService, settingsService) {
        this.ahttp = ahttp;
        this.bulletinSecretService = bulletinSecretService;
        this.settingsService = settingsService;
        this.walletError = false;
        this.wallet = {};
    }
    WalletService.prototype.get = function (fastgraph) {
        var _this = this;
        if (fastgraph === void 0) { fastgraph = true; }
        return new Promise(function (resolve, reject) {
            if (!_this.settingsService.remoteSettings['walletUrl'])
                return resolve();
            _this.bulletinSecretService.get()
                .then(function () {
                return _this.walletPromise();
            })
                .then(function () {
                return resolve();
            })
                .catch(function () {
                return reject();
            });
        });
    };
    WalletService.prototype.walletPromise = function (amount_needed) {
        var _this = this;
        if (amount_needed === void 0) { amount_needed = 0; }
        return new Promise(function (resolve, reject) {
            if (!_this.settingsService.remoteSettings['walletUrl']) {
                return reject();
            }
            if (_this.bulletinSecretService.username) {
                var headers = new __WEBPACK_IMPORTED_MODULE_3__angular_http__["a" /* Headers */]();
                headers.append('Authorization', 'Bearer ' + _this.settingsService.tokens[_this.bulletinSecretService.keyname]);
                var options = new __WEBPACK_IMPORTED_MODULE_3__angular_http__["d" /* RequestOptions */]({ headers: headers, withCredentials: true });
                _this.ahttp.get(_this.settingsService.remoteSettings['walletUrl'] + '?amount_needed=' + amount_needed + '&address=' + _this.bulletinSecretService.key.getAddress() + '&bulletin_secret=' + _this.bulletinSecretService.bulletin_secret + '&origin=' + window.location.origin, options).
                    subscribe(function (data) {
                    if (data['_body']) {
                        _this.walletError = false;
                        _this.wallet = JSON.parse(data['_body']);
                        _this.wallet.balancePretty = _this.wallet.balance.toFixed(2);
                        resolve(data['_body']);
                    }
                    else {
                        _this.walletError = true;
                        _this.wallet = {};
                        _this.wallet.balancePretty = 0;
                        reject("no data returned");
                    }
                }, function (err) {
                    _this.walletError = true;
                    reject("data or server error");
                });
            }
            else {
                _this.walletError = true;
                reject("username not set");
            }
        });
    };
    WalletService = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["B" /* Injectable */])(),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_3__angular_http__["b" /* Http */],
            __WEBPACK_IMPORTED_MODULE_1__bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_2__settings_service__["a" /* SettingsService */]])
    ], WalletService);
    return WalletService;
}());

//# sourceMappingURL=wallet.service.js.map

/***/ }),

/***/ 258:
/***/ (function(module, exports) {

function webpackEmptyAsyncContext(req) {
	// Here Promise.resolve().then() is used instead of new Promise() to prevent
	// uncatched exception popping up in devtools
	return Promise.resolve().then(function() {
		throw new Error("Cannot find module '" + req + "'.");
	});
}
webpackEmptyAsyncContext.keys = function() { return []; };
webpackEmptyAsyncContext.resolve = webpackEmptyAsyncContext;
module.exports = webpackEmptyAsyncContext;
webpackEmptyAsyncContext.id = 258;

/***/ }),

/***/ 302:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return PostModal; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__app_wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_transaction_service__ = __webpack_require__(34);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_opengraphparser_service__ = __webpack_require__(109);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_settings_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__angular_http__ = __webpack_require__(18);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};








var PostModal = /** @class */ (function () {
    function PostModal(navParams, viewCtrl, walletService, alertCtrl, transactionService, openGraphParserService, settingsService, ahttp) {
        var _this = this;
        this.navParams = navParams;
        this.viewCtrl = viewCtrl;
        this.walletService = walletService;
        this.alertCtrl = alertCtrl;
        this.transactionService = transactionService;
        this.openGraphParserService = openGraphParserService;
        this.settingsService = settingsService;
        this.ahttp = ahttp;
        this.blockchainAddress = null;
        this.postText = null;
        this.logicalParent = null;
        this.post = {};
        this.files = null;
        this.selectedFile = null;
        this.blockchainAddress = navParams.data.blockchainAddress;
        this.logicalParent = navParams.data.logicalParent;
        var headers = new __WEBPACK_IMPORTED_MODULE_6__angular_http__["a" /* Headers */]();
        headers.append('Authorization', 'basic ' + Base64.encode(this.settingsService.remoteSettings['siaPassword']));
        var options = new __WEBPACK_IMPORTED_MODULE_6__angular_http__["d" /* RequestOptions */]({ headers: headers, withCredentials: true });
        this.ahttp.get(this.settingsService.remoteSettings['siaUrl'] + '/renter/files', options)
            .subscribe(function (res) {
            _this.files = res.json()['files'];
        });
    }
    PostModal.prototype.change = function () {
        var _this = this;
        if (this.openGraphParserService.isURL(this.postText)) {
            this.openGraphParserService.parseFromUrl(this.postText).then(function (data) {
                _this.post = data;
            });
        }
    };
    PostModal.prototype.submit = function () {
        var _this = this;
        this.walletService.get().then(function () {
            return new Promise(function (resolve, reject) {
                if (_this.selectedFile) {
                    _this.ahttp.get(_this.settingsService.remoteSettings['siaUrl'] + '/renter/shareascii?siapaths=' + _this.selectedFile[0])
                        .subscribe(function (res) {
                        var sharefiledata = res.json()['asciisia'];
                        _this.approveTxn(sharefiledata, resolve);
                    });
                }
                else {
                    _this.approveTxn(null, resolve);
                }
                console.log(status);
            }).then(function () {
                _this.dismiss();
            });
        });
    };
    PostModal.prototype.approveTxn = function (sharefiledata, resolve) {
        var _this = this;
        var alert = this.alertCtrl.create();
        alert.setTitle('Approve Transaction');
        alert.setSubTitle('You are about to spend 0.01 coins ( 0.01 fee)');
        alert.addButton('Cancel');
        alert.addButton({
            text: 'Confirm',
            handler: function (data) {
                // camera permission was granted
                new Promise(function (resolve, reject) {
                    if (sharefiledata) {
                        return _this.transactionService.generateTransaction({
                            relationship: {
                                postText: _this.postText,
                                postFile: sharefiledata,
                                postFileName: _this.selectedFile[0]
                            }
                        })
                            .then(function () {
                            resolve();
                        })
                            .catch(function (err) {
                            reject();
                        });
                    }
                    else {
                        return _this.transactionService.generateTransaction({
                            relationship: {
                                postText: _this.postText
                            }
                        })
                            .then(function () {
                            resolve();
                        })
                            .catch(function (err) {
                            reject();
                        });
                    }
                })
                    .then(function () {
                    return _this.transactionService.getFastGraphSignature();
                })
                    .then(function (hash) {
                    return _this.transactionService.sendTransaction();
                })
                    .then(function () {
                    _this.dismiss();
                })
                    .catch(function (err) {
                    console.log('could not generate hash');
                });
            }
        });
        alert.present();
    };
    PostModal.prototype.dismiss = function () {
        this.logicalParent.refresh();
        this.viewCtrl.dismiss();
    };
    PostModal = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["n" /* Component */])({
            selector: 'modal-post',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/home/postmodal.html"*/'<ion-header>\n  <ion-toolbar>\n    <ion-title>\n      Write post\n    </ion-title>\n    <ion-buttons start>\n      <button ion-button (click)="dismiss()">\n        <span ion-text color="primary" showWhen="ios">Cancel</span>\n        <ion-icon name="md-close" showWhen="android,windows,core"></ion-icon>\n      </button>\n    </ion-buttons>\n  </ion-toolbar>\n</ion-header>\n<ion-content>\n  <ion-item>\n    <ion-textarea placeholder="Shortened url (35 chars max)" [(ngModel)]="postText" (input)="change()">\n    </ion-textarea>\n  </ion-item>\n  <ion-item>\n    <ion-label>Files</ion-label>\n    <ion-select [(ngModel)]="selectedFile" multiple="true">\n      <ion-option *ngFor="let file of files" value="{{file.siapath}}">{{file.siapath}}</ion-option>\n    </ion-select>\n  </ion-item>\n  <button ion-button secondary (click)="submit()">Post</button>\n  <ion-card *ngIf="post.title">\n    <img src="{{post.image}}" *ngIf="post.image" />\n    <ion-card-content>\n      <ion-card-title>\n        {{post.title}}\n      </ion-card-title>\n      <p *ngIf="post.description">\n        {{post.description}}\n      </p>\n    </ion-card-content>\n  </ion-card>\n</ion-content>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/home/postmodal.html"*/
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["j" /* NavParams */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["m" /* ViewController */],
            __WEBPACK_IMPORTED_MODULE_2__app_wallet_service__["a" /* WalletService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["a" /* AlertController */],
            __WEBPACK_IMPORTED_MODULE_3__app_transaction_service__["a" /* TransactionService */],
            __WEBPACK_IMPORTED_MODULE_4__app_opengraphparser_service__["a" /* OpenGraphParserService */],
            __WEBPACK_IMPORTED_MODULE_5__app_settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_6__angular_http__["b" /* Http */]])
    ], PostModal);
    return PostModal;
}());

//# sourceMappingURL=postmodal.js.map

/***/ }),

/***/ 304:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return CompleteTestService; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__settings_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__bulletinSecret_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__angular_http__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4_rxjs_add_operator_map__ = __webpack_require__(490);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4_rxjs_add_operator_map___default = __webpack_require__.n(__WEBPACK_IMPORTED_MODULE_4_rxjs_add_operator_map__);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};





var CompleteTestService = /** @class */ (function () {
    function CompleteTestService(http, settingsService, bulletinSecretService) {
        this.http = http;
        this.settingsService = settingsService;
        this.bulletinSecretService = bulletinSecretService;
        this.labelAttribute = "name";
        this.formValueAttribute = "value";
    }
    CompleteTestService.prototype.getResults = function (searchTerm) {
        return this.http.get(this.settingsService.remoteSettings['baseUrl'] + '/ns?searchTerm=' + searchTerm + '&bulletin_secret=' + this.bulletinSecretService.bulletin_secret)
            .map(function (res) {
            var result = res.json().map(function (item) {
                return { name: item.relationship.their_username, value: item };
            });
            return result;
        });
    };
    CompleteTestService = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["B" /* Injectable */])(),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_3__angular_http__["b" /* Http */],
            __WEBPACK_IMPORTED_MODULE_1__settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_2__bulletinSecret_service__["a" /* BulletinSecretService */]])
    ], CompleteTestService);
    return CompleteTestService;
}());

//# sourceMappingURL=autocomplete.provider.js.map

/***/ }),

/***/ 305:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return Settings; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__ionic_storage__ = __webpack_require__(33);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_settings_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_peer_service__ = __webpack_require__(181);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_bulletinSecret_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_firebase_service__ = __webpack_require__(185);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__list_list__ = __webpack_require__(51);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__app_graph_service__ = __webpack_require__(40);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__app_wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_10__ionic_native_social_sharing__ = __webpack_require__(85);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_11__home_home__ = __webpack_require__(180);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};














var Settings = /** @class */ (function () {
    function Settings(navCtrl, navParams, settingsService, bulletinSecretService, firebaseService, loadingCtrl, alertCtrl, storage, graphService, socialSharing, walletService, events, toastCtrl, peerService) {
        this.navCtrl = navCtrl;
        this.navParams = navParams;
        this.settingsService = settingsService;
        this.bulletinSecretService = bulletinSecretService;
        this.firebaseService = firebaseService;
        this.loadingCtrl = loadingCtrl;
        this.alertCtrl = alertCtrl;
        this.storage = storage;
        this.graphService = graphService;
        this.socialSharing = socialSharing;
        this.walletService = walletService;
        this.events = events;
        this.toastCtrl = toastCtrl;
        this.peerService = peerService;
        this.baseUrl = null;
        this.blockchainAddress = null;
        this.graphproviderAddress = null;
        this.walletproviderAddress = null;
        this.siaAddress = null;
        this.siaPassword = null;
        this.keys = null;
        this.loadingModal = null;
        this.prefix = null;
        this.importedKey = null;
        this.activeKey = null;
        this.serverDown = false;
        this.noUsername = false;
        this.key = null;
        this.favorites = null;
        this.removeFavorites = null;
        this.refresh(null).catch(function (err) {
            console.log(err);
        });
        this.prefix = 'usernames-';
    }
    Settings.prototype.refresh = function (refresher) {
        var _this = this;
        this.noUsername = false;
        return this.bulletinSecretService.all().then(function (keys) {
            _this.setKey(keys);
        }).then(function () {
            _this.getFavorites();
        }).then(function () {
            if (refresher)
                refresher.complete();
        });
    };
    Settings.prototype.saveToFavorites = function () {
        var _this = this;
        var alert = this.alertCtrl.create({
            title: 'Set group name',
            inputs: [
                {
                    name: 'groupname',
                    placeholder: 'Group name'
                }
            ],
            buttons: [
                {
                    text: 'Save',
                    handler: function (data) {
                        _this.storage.set('favorites-' + data.groupname, _this.settingsService.remoteSettingsUrl);
                        _this.getFavorites();
                    }
                }
            ]
        });
        alert.present();
    };
    Settings.prototype.getResults = function (keyword) {
        return ['234234', '234234'];
    };
    Settings.prototype.getFavorites = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            var favorites = [];
            _this.storage.forEach(function (value, key) {
                if (key.substr(0, 'favorites-'.length) === 'favorites-') {
                    favorites.push({ label: key.substr('favorites-'.length), url: value });
                }
            })
                .then(function () {
                if (favorites.length == 0) {
                    var host = window.location.protocol + '//' + window.location.host;
                    _this.storage.set('favorites-Home', host);
                    favorites.push({ label: 'Home', url: host });
                }
                _this.favorites = favorites;
                resolve(favorites);
            });
        });
    };
    Settings.prototype.selectFavorite = function (favorite) {
        for (var i = 0; i < this.favorites.length; i++) {
            this.favorites[i].active = false;
        }
        favorite.active = true;
        this.settingsService.remoteSettingsUrl = favorite.url;
        this.storage.set('node', favorite.url);
    };
    Settings.prototype.removeFavorite = function (favorite) {
        var _this = this;
        this.storage.remove('favorites-' + favorite.label);
        this.getFavorites()
            .then(function (favorites) {
            if (!favorites) {
                _this.removeFavorites = null;
            }
        });
    };
    Settings.prototype.setKey = function (keys) {
        var _this = this;
        var keys_indexed = {};
        for (var i = 0; i < keys.length; i++) {
            keys_indexed[keys[i].key] = keys[i].key;
        }
        var newKeys = [];
        this.storage.forEach(function (value, key) {
            if (key.substr(0, _this.prefix.length) === _this.prefix) {
                var active = (_this.bulletinSecretService.username || '') == key.substr(_this.prefix.length);
                newKeys.push({
                    username: key.substr(_this.prefix.length),
                    key: value,
                    active: active
                });
                if (active) {
                    _this.activeKey = value;
                }
            }
        })
            .then(function () {
            newKeys.sort(function (a, b) {
                if (a.username < b.username)
                    return -1;
                if (a.username > b.username)
                    return 1;
                return 0;
            });
            _this.keys = newKeys;
        });
    };
    Settings.prototype.exportKey = function () {
        var _this = this;
        var alert = this.alertCtrl.create();
        alert.setTitle('Export Key');
        alert.setSubTitle('Warning: Never ever share this secret key with anybody but yourself!');
        alert.addButton({
            text: 'Ok',
            handler: function (data) {
                _this.socialSharing.share(_this.bulletinSecretService.key.toWIF(), "Export Secret Key");
            }
        });
        alert.present();
    };
    Settings.prototype.importKey = function () {
        var _this = this;
        new Promise(function (resolve, reject) {
            var alert = _this.alertCtrl.create({
                title: 'Set username',
                inputs: [
                    {
                        name: 'username',
                        placeholder: 'Username'
                    }
                ],
                buttons: [
                    {
                        text: 'Cancel',
                        role: 'cancel',
                        handler: function (data) {
                            console.log('Cancel clicked');
                            reject();
                        }
                    },
                    {
                        text: 'Save',
                        handler: function (data) {
                            var toast = _this.toastCtrl.create({
                                message: 'Identity created',
                                duration: 2000
                            });
                            toast.present();
                            resolve(data.username);
                        }
                    }
                ]
            });
            alert.present();
        })
            .then(function (username) {
            return _this.bulletinSecretService.import(_this.importedKey, username);
        })
            .then(function () {
            _this.importedKey = '';
            return _this.refresh(null);
        })
            .catch(function () {
            var toast = _this.toastCtrl.create({
                message: 'Error importing identity!',
                duration: 2000
            });
            toast.present();
        });
    };
    Settings.prototype.createKey = function () {
        var _this = this;
        new Promise(function (resolve, reject) {
            var alert = _this.alertCtrl.create({
                title: 'Set username',
                inputs: [
                    {
                        name: 'username',
                        placeholder: 'Username'
                    }
                ],
                buttons: [
                    {
                        text: 'Cancel',
                        role: 'cancel',
                        handler: function (data) {
                            console.log('Cancel clicked');
                            reject();
                        }
                    },
                    {
                        text: 'Save',
                        handler: function (data) {
                            var toast = _this.toastCtrl.create({
                                message: 'Identity created',
                                duration: 2000
                            });
                            toast.present();
                            resolve(data.username);
                        }
                    }
                ]
            });
            alert.present();
        })
            .then(function (username) {
            return _this.bulletinSecretService.create(username);
        })
            .then(function () {
            return _this.doSet(_this.bulletinSecretService.keyname);
        })
            .then(function () {
            if (_this.settingsService.remoteSettings['walletUrl']) {
                return _this.graphService.getInfo();
            }
        })
            .then(function () {
            return _this.refresh(null);
        })
            .then(function () {
            _this.events.publish('pages-settings');
        })
            .catch(function () {
            _this.events.publish('pages');
        });
    };
    Settings.prototype.selectIdentity = function (key) {
        var _this = this;
        var toast = this.toastCtrl.create({
            message: 'Now click the "go" button',
            duration: 2000
        });
        toast.present();
        this.set(key)
            .then(function () {
            _this.save();
        });
    };
    Settings.prototype.set = function (key) {
        var _this = this;
        this.storage.set('last-keyname', this.prefix + key);
        return this.doSet(this.prefix + key)
            .then(function () {
            _this.events.publish('pages-settings');
        })
            .catch(function () {
            console.log('can not set identity');
        });
    };
    Settings.prototype.doSet = function (keyname) {
        var _this = this;
        return new Promise(function (resolve, reject) {
            _this.bulletinSecretService.set(keyname).then(function () {
                return _this.refresh(null);
            }).then(function () {
                _this.serverDown = false;
                if (!document.URL.startsWith('http') || document.URL.startsWith('http://localhost:8080')) {
                    _this.firebaseService.initFirebase();
                }
                return resolve();
            }).catch(function (error) {
                _this.serverDown = true;
                return reject();
            });
        });
    };
    Settings.prototype.save = function () {
        var _this = this;
        this.loadingModal = this.loadingCtrl.create({
            content: 'Please wait...'
        });
        this.loadingModal.present();
        this.graphService.graph = {
            comments: "",
            reacts: "",
            commentReacts: ""
        };
        this.peerService.go()
            .then(function () {
            return _this.set(_this.bulletinSecretService.keyname.substr(_this.prefix.length));
        })
            .then(function () {
            _this.navCtrl.setRoot(__WEBPACK_IMPORTED_MODULE_11__home_home__["a" /* HomePage */]);
        })
            .then(function () {
            _this.loadingModal.dismiss();
        })
            .catch(function (err) {
            _this.loadingModal.dismiss();
        });
    };
    Settings.prototype.showChat = function () {
        var item = { pageTitle: { title: "Chat" } };
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_7__list_list__["a" /* ListPage */], item);
    };
    Settings.prototype.showFriendRequests = function () {
        var item = { pageTitle: { title: "Friend Requests" } };
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_7__list_list__["a" /* ListPage */], item);
    };
    Settings = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["n" /* Component */])({
            selector: 'page-settings',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/settings/settings.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n    <ion-item *ngIf="peerService.mode">\n      <a button clear href="https://youtube.com/w=lajksdf98" target="_blank" item-start>\n        <ion-icon large name="help-circle"></ion-icon>\n      </a>\n      <ion-label color="primary" text-right>Node address: </ion-label>\n      <ion-input color="primary" type="text" placeholder="Enter a url" [(ngModel)]="settingsService.remoteSettingsUrl"></ion-input>\n      <button ion-button primary (click)="saveToFavorites()" item-end>Save</button>\n    </ion-item>\n  </ion-navbar>\n</ion-header>\n\n<ion-content padding>\n  <ion-refresher (ionRefresh)="refresh($event)">\n    <ion-refresher-content></ion-refresher-content>\n  </ion-refresher>\n  <ion-item col-md-2>\n    <ion-toggle color="primary" class="wallet-toggle" [(ngModel)]="peerService.mode"></ion-toggle>\n    <ion-label>Manual mode</ion-label>\n  </ion-item>\n  <h3 *ngIf="peerService.mode">Nodes</h3>\n  <ion-list *ngIf="peerService.mode">\n    <ion-row>\n      <ion-col col-lg-3 col-md-4 col-sm-4 *ngFor="let favorite of favorites">\n        <button ion-item (click)="selectFavorite(favorite)" [color]="favorite.active ? \'secondary\' : \'dark\'">\n          <ion-card padding>\n            <img src="assets/img/yadacoinlogotextsmall.png">\n            <ion-card-content>\n              <ion-card-title style="text-overflow:ellipsis;" text-wrap>\n                  {{favorite.label}}\n              </ion-card-title>\n            </ion-card-content>\n          </ion-card>\n        </button>\n      </ion-col>\n    </ion-row>\n  </ion-list>\n  <h3>Identities</h3>\n  <button ion-button secondary (click)="createKey()">Create identity</button>\n  <ion-list>\n    <ion-row>\n      <ion-col col-lg-3 col-md-4 col-sm-4 *ngFor="let key of keys">\n        <button ion-item (click)="selectIdentity(key.username)" [color]="key.active ? \'secondary\' : \'dark\'">\n          <ion-card padding>\n            <img src="assets/img/yadacoinlogotextsmall.png">\n            <ion-card-content>\n              <ion-card-title style="text-overflow:ellipsis;" text-wrap>\n                  {{key.username}}\n              </ion-card-title>\n            </ion-card-content>\n          </ion-card>\n        </button>\n      </ion-col>\n    </ion-row>\n  </ion-list>\n  <ion-list *ngIf="bulletinSecretService.keyname">\n    <hr/>\n    <h4>Export identity</h4>\n    <ion-item>\n      <ion-input type="text" [(ngModel)]="activeKey">\n      </ion-input>\n    </ion-item>\n    <h4>Bulletin secret</h4>\n    <ion-item>\n      <ion-input type="text" [(ngModel)]="bulletinSecretService.bulletin_secret">\n      </ion-input>\n      <button ion-button secondary (click)="exportKey()">Export active identity</button>\n    </ion-item>\n  </ion-list>\n  <ion-list>\n    <h4>Import identity</h4>\n    <ion-item>\n      <ion-input type="text" placeholder="Paste WIF key from your wallet..." [(ngModel)]="importedKey">\n      </ion-input>\n    </ion-item>\n    <button ion-button secondary (click)="importKey()">Import identity</button>\n  </ion-list>\n</ion-content>\n'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/settings/settings.html"*/
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["i" /* NavController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["j" /* NavParams */],
            __WEBPACK_IMPORTED_MODULE_3__app_settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_5__app_bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_6__app_firebase_service__["a" /* FirebaseService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["f" /* LoadingController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["a" /* AlertController */],
            __WEBPACK_IMPORTED_MODULE_2__ionic_storage__["b" /* Storage */],
            __WEBPACK_IMPORTED_MODULE_8__app_graph_service__["a" /* GraphService */],
            __WEBPACK_IMPORTED_MODULE_10__ionic_native_social_sharing__["a" /* SocialSharing */],
            __WEBPACK_IMPORTED_MODULE_9__app_wallet_service__["a" /* WalletService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["b" /* Events */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["l" /* ToastController */],
            __WEBPACK_IMPORTED_MODULE_4__app_peer_service__["a" /* PeerService */]])
    ], Settings);
    return Settings;
}());

//# sourceMappingURL=settings.js.map

/***/ }),

/***/ 306:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return StreamPage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__ionic_storage__ = __webpack_require__(33);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_graph_service__ = __webpack_require__(40);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_bulletinSecret_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_transaction_service__ = __webpack_require__(34);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__app_settings_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__angular_http__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__angular_platform_browser__ = __webpack_require__(46);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};











var StreamPage = /** @class */ (function () {
    function StreamPage(navCtrl, navParams, storage, walletService, transactionService, alertCtrl, graphService, loadingCtrl, bulletinSecretService, settingsService, ahttp, modalCtrl, toastCtrl, dom) {
        var _this = this;
        this.navCtrl = navCtrl;
        this.navParams = navParams;
        this.storage = storage;
        this.walletService = walletService;
        this.transactionService = transactionService;
        this.alertCtrl = alertCtrl;
        this.graphService = graphService;
        this.loadingCtrl = loadingCtrl;
        this.bulletinSecretService = bulletinSecretService;
        this.settingsService = settingsService;
        this.ahttp = ahttp;
        this.modalCtrl = modalCtrl;
        this.toastCtrl = toastCtrl;
        this.dom = dom;
        this.streams = {};
        this.label = this.navParams.get('pageTitle').label;
        // if (this.showLoading) {
        //     this.loading = true;
        // }
        this.getSiaFiles()
            .then(function () {
            _this.graphService.getGroups();
        })
            .then(function () {
            return new Promise(function (resolve, reject) {
                for (var i = 0; i < _this.graphService.graph.groups.length; i++) {
                    var group = _this.graphService.graph.groups[i];
                    if (!_this.streams[group.rid]) {
                        _this.streams[group.rid] = [];
                    }
                }
                resolve();
            });
        })
            .then(function () {
            var promises = [];
            for (var i = 0; i < _this.graphService.graph.groups.length; i++) {
                var group = _this.graphService.graph.groups[i];
                promises.push(_this.getGroupMessages(group));
            }
            return Promise.all(promises);
        })
            .then(function (groups) {
            var promises = [];
            for (var i = 0; i < groups.length; i++) {
                var group = groups[i];
                promises.push(_this.parseChats(group));
            }
            return Promise.all(promises);
        })
            .then(function (groups) {
            _this.i = 0;
            _this.j = 0;
            _this.groups = groups;
            _this.cycleMedia();
            setInterval(function () { return _this.cycleMedia(); }, 1200000);
        })
            .catch(function (err) {
            _this.error = true;
            console.log(err);
        });
    }
    StreamPage.prototype.selectGroup = function (rid) {
        this.selectedGroup = rid;
        this.cycleMedia();
    };
    StreamPage.prototype.cycleMedia = function () {
        var _this = this;
        if (this.error)
            return;
        if (!this.groups[this.i]) {
            this.i = 0;
            if (!this.groups[this.i]) {
                return;
            }
        }
        var group = this.groups[this.i];
        var rid = this.selectedGroup || group.rid;
        if (!this.streams[rid][this.j]) {
            if (this.j === 0) {
                this.i = 0;
                var group = this.groups[this.i];
            }
            else {
                this.j = 0;
            }
        }
        var stream = this.streams[rid][this.j];
        this.ahttp.get(stream.url)
            .subscribe(function (res) {
            _this.streamUrl = stream.url;
            _this.j += 1;
        }, function (err) {
            _this.import(stream.relationship);
            _this.j += 1;
            if (!_this.streams[rid][_this.j]) {
                _this.selectedGroup = null;
                _this.i += 1;
                _this.j = 0;
            }
            setTimeout(function () { _this.cycleMedia(); }, 5000);
        });
    };
    StreamPage.prototype.import = function (relationship) {
        var _this = this;
        return this.ahttp.post(this.settingsService.remoteSettings['baseUrl'] + '/sia-share-file?origin=' + encodeURIComponent(window.location.origin), relationship)
            .subscribe(function (res) {
            console.log('New file imported:');
            console.log(res.json());
            var files = res.json();
        }, function (err) {
            _this.error = true;
        });
    };
    StreamPage.prototype.getGroupMessages = function (group) {
        var _this = this;
        return new Promise(function (resolve, reject) {
            _this.graphService.getGroupMessages(group['relationship']['their_bulletin_secret'], null, group.rid)
                .then(function () {
                return resolve(group);
            });
        });
    };
    StreamPage.prototype.parseChats = function (group) {
        var _this = this;
        return new Promise(function (resolve, reject) {
            if (!_this.graphService.graph['messages'][group.rid])
                return resolve(group);
            for (var j = 0; j < _this.graphService.graph['messages'][group.rid].length; j++) {
                var message = _this.graphService.graph['messages'][group.rid][j];
                if (message['relationship']['groupChatFileName']) {
                    _this.streams[group.rid].push({
                        url: _this.settingsService.remoteSettings['baseUrl'] + '/sia-files-stream?siapath=' + message['relationship']['groupChatFileName'],
                        title: '',
                        relationship: message['relationship']
                    });
                }
            }
            if (_this.streams[group.rid].length === 0) {
                delete _this.streams[group.rid];
            }
            resolve(group);
        });
    };
    StreamPage.prototype.sanitize = function (url) {
        return this.dom.bypassSecurityTrustResourceUrl(url);
    };
    StreamPage.prototype.getSiaFiles = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            _this.ahttp.get(_this.settingsService.remoteSettings['baseUrl'] + '/sia-files')
                .subscribe(function (res) {
                var files = res.json();
                resolve(files);
            }, function (err) {
                _this.error = true;
                reject(_this.error);
            });
        });
    };
    StreamPage = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["n" /* Component */])({
            selector: 'page-stream',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/stream/stream.html"*/'<ion-header>\n    <ion-navbar>\n        <button ion-button menuToggle color="{{color}}">\n            <ion-icon name="menu"></ion-icon>\n        </button>\n        <ion-title>{{label}}</ion-title>\n    </ion-navbar>\n</ion-header>\n<ion-content>\n    <ion-list *ngIf="!error">\n        <button ion-item *ngFor="let group of groups" (click)="selectGroup(group.requested_rid || group.rid)">{{group.relationship.their_username}}</button>\n    </ion-list>\n    <iframe [src]="sanitize(streamUrl)" width="100%" height="100%" border="0" *ngIf="streamUrl && !error" id="iframe"></iframe>\n    <ion-item *ngIf="error">You must download the <a href="https://github.com/pdxwebdev/yadacoin/releases/latest" target="_blank">full node</a> to stream content from the blockchain.</ion-item>\n</ion-content>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/stream/stream.html"*/,
            queries: {
                content: new __WEBPACK_IMPORTED_MODULE_0__angular_core__["_14" /* ViewChild */]('content')
            }
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["i" /* NavController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["j" /* NavParams */],
            __WEBPACK_IMPORTED_MODULE_2__ionic_storage__["b" /* Storage */],
            __WEBPACK_IMPORTED_MODULE_5__app_wallet_service__["a" /* WalletService */],
            __WEBPACK_IMPORTED_MODULE_6__app_transaction_service__["a" /* TransactionService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["a" /* AlertController */],
            __WEBPACK_IMPORTED_MODULE_3__app_graph_service__["a" /* GraphService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["f" /* LoadingController */],
            __WEBPACK_IMPORTED_MODULE_4__app_bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_7__app_settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_8__angular_http__["b" /* Http */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["g" /* ModalController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["l" /* ToastController */],
            __WEBPACK_IMPORTED_MODULE_9__angular_platform_browser__["c" /* DomSanitizer */]])
    ], StreamPage);
    return StreamPage;
}());

//# sourceMappingURL=stream.js.map

/***/ }),

/***/ 307:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return SendReceive; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__app_wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_transaction_service__ = __webpack_require__(34);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_bulletinSecret_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__ionic_native_qr_scanner__ = __webpack_require__(308);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_settings_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__ionic_native_social_sharing__ = __webpack_require__(85);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__list_list__ = __webpack_require__(51);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__angular_http__ = __webpack_require__(18);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};











var SendReceive = /** @class */ (function () {
    function SendReceive(navCtrl, qrScanner, transactionService, alertCtrl, bulletinSecretService, walletService, socialSharing, loadingCtrl, ahttp, settingsService) {
        var _this = this;
        this.navCtrl = navCtrl;
        this.qrScanner = qrScanner;
        this.transactionService = transactionService;
        this.alertCtrl = alertCtrl;
        this.bulletinSecretService = bulletinSecretService;
        this.walletService = walletService;
        this.socialSharing = socialSharing;
        this.loadingCtrl = loadingCtrl;
        this.ahttp = ahttp;
        this.settingsService = settingsService;
        this.value = null;
        this.createdCode = null;
        this.address = null;
        this.balance = null;
        this.isDevice = null;
        this.loadingModal = this.loadingCtrl.create({
            content: 'Please wait...'
        });
        this.value = 0;
        this.bulletinSecretService.get().then(function () {
            _this.createdCode = bulletinSecretService.key.getAddress();
            _this.refresh();
        });
    }
    SendReceive.prototype.scan = function () {
        var _this = this;
        if (!document.URL.startsWith('http') || document.URL.startsWith('http://localhost:8080')) {
            this.isDevice = true;
        }
        else {
            this.isDevice = false;
        }
        this.qrScanner.prepare().then(function (status) {
            console.log(status);
            if (status.authorized) {
                // start scanning
                var scanSub_1 = _this.qrScanner.scan().subscribe(function (text) {
                    console.log('Scanned address', text);
                    _this.address = text;
                    _this.qrScanner.hide(); // hide camera preview
                    scanSub_1.unsubscribe(); // stop scanning
                    window.document.querySelector('ion-app').classList.remove('transparentBody');
                });
            }
        });
        this.qrScanner.resumePreview();
        // show camera preview
        this.qrScanner.show();
        window.document.querySelector('ion-app').classList.add('transparentBody');
    };
    SendReceive.prototype.submit = function () {
        var _this = this;
        var value = parseFloat(this.value);
        var total = value + 0.01;
        var alert = this.alertCtrl.create();
        if (!this.address) {
            alert.setTitle('Enter an address');
            alert.addButton('Ok');
            alert.present();
            return;
        }
        if (!value) {
            alert.setTitle('Enter an amount');
            alert.addButton('Ok');
            alert.present();
            return;
        }
        alert.setTitle('Approve Transaction');
        alert.setSubTitle('You are about to spend ' + total + ' coins (' + this.value + ' coin + 0.001 fee)');
        alert.addButton('Cancel');
        alert.addButton({
            text: 'Confirm',
            handler: function (data) {
                _this.loadingModal.present();
                _this.walletService.get(_this.value)
                    .then(function () {
                    return _this.transactionService.generateTransaction({
                        to: _this.address,
                        value: value
                    });
                }).then(function () {
                    return _this.transactionService.sendTransaction();
                }).then(function (txn) {
                    var title = 'Transaction Sent';
                    var message = 'Your transaction has been sent succefully.';
                    if (!txn) {
                        title = 'Insufficient Funds';
                        message = "Not enough YadaCoins for transaction.";
                    }
                    var alert = _this.alertCtrl.create();
                    alert.setTitle(title);
                    alert.setSubTitle(message);
                    alert.addButton('Ok');
                    alert.present();
                    _this.value = null;
                    _this.address = null;
                    _this.refresh();
                    _this.loadingModal.dismiss().catch(function () { });
                })
                    .catch(function (err) {
                    console.log(err);
                    _this.loadingModal.dismiss().catch(function () { });
                });
            }
        });
        alert.present();
    };
    SendReceive.prototype.refresh = function () {
        var _this = this;
        this.loadingBalance = true;
        return this.walletService.get(this.value)
            .then(function () {
            _this.loadingBalance = false;
            _this.balance = _this.walletService.wallet.balance;
        }).catch(function (err) {
            console.log(err);
        });
    };
    SendReceive.prototype.shareAddress = function () {
        this.socialSharing.share(this.bulletinSecretService.key.getAddress(), "Send Yada Coin to this address!");
    };
    SendReceive.prototype.showChat = function () {
        var item = { pageTitle: { title: "Chat" } };
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_8__list_list__["a" /* ListPage */], item);
    };
    SendReceive.prototype.showFriendRequests = function () {
        var item = { pageTitle: { title: "Friend Requests" } };
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_8__list_list__["a" /* ListPage */], item);
    };
    SendReceive = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["n" /* Component */])({
            selector: 'page-sendreceive',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/sendreceive/sendreceive.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n  </ion-navbar>\n</ion-header>\n<ion-content padding>\n  <ion-refresher (ionRefresh)="refresh($event)">\n    <ion-refresher-content></ion-refresher-content>\n  </ion-refresher>\n  <h4>Balance</h4>\n  <ion-item>\n    {{walletService.wallet.balance}} YADA\n  </ion-item>\n  <h4>Send YadaCoins</h4>\n  <button *ngIf="isDevice" ion-button color="secondary" (click)="scan()" full>Scan Address</button>\n  <ion-item>\n    <ion-label color="primary" stacked>Address</ion-label>\n    <ion-input type="text" placeholder="Recipient address..." [(ngModel)]="address">\n    </ion-input>\n  </ion-item>\n  <ion-item>\n    <ion-label color="primary" fixed>Amount</ion-label>\n    <ion-input type="number" placeholder="Amount..." [(ngModel)]="value">\n    </ion-input>\n  </ion-item>\n  <button ion-button secondary (click)="submit()">Send</button>\n  <h4>Receive YadaCoins</h4>\n  <ion-item>\n    <ion-label color="primary" stacked>Your Address:</ion-label>\n    <ion-input type="text" [(ngModel)]="createdCode"></ion-input>\n  </ion-item>\n  <button *ngIf="isDevice" ion-button outline item-end (click)="shareAddress()">share address&nbsp;<ion-icon name="share"></ion-icon></button>\n  <ion-card>\n    <ion-card-content>\n      <ngx-qrcode [qrc-value]="createdCode"></ngx-qrcode>\n    </ion-card-content>\n  </ion-card>\n</ion-content>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/sendreceive/sendreceive.html"*/
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["i" /* NavController */],
            __WEBPACK_IMPORTED_MODULE_5__ionic_native_qr_scanner__["a" /* QRScanner */],
            __WEBPACK_IMPORTED_MODULE_3__app_transaction_service__["a" /* TransactionService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["a" /* AlertController */],
            __WEBPACK_IMPORTED_MODULE_4__app_bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_2__app_wallet_service__["a" /* WalletService */],
            __WEBPACK_IMPORTED_MODULE_7__ionic_native_social_sharing__["a" /* SocialSharing */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["f" /* LoadingController */],
            __WEBPACK_IMPORTED_MODULE_9__angular_http__["b" /* Http */],
            __WEBPACK_IMPORTED_MODULE_6__app_settings_service__["a" /* SettingsService */]])
    ], SendReceive);
    return SendReceive;
}());

//# sourceMappingURL=sendreceive.js.map

/***/ }),

/***/ 326:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
Object.defineProperty(__webpack_exports__, "__esModule", { value: true });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_platform_browser_dynamic__ = __webpack_require__(327);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__app_module__ = __webpack_require__(437);


Object(__WEBPACK_IMPORTED_MODULE_0__angular_platform_browser_dynamic__["a" /* platformBrowserDynamic */])().bootstrapModule(__WEBPACK_IMPORTED_MODULE_1__app_module__["a" /* AppModule */]);
//# sourceMappingURL=main.js.map

/***/ }),

/***/ 34:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return TransactionService; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__bulletinSecret_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__settings_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__angular_http__ = __webpack_require__(18);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};





var TransactionService = /** @class */ (function () {
    function TransactionService(walletService, bulletinSecretService, ahttp, settingsService) {
        this.walletService = walletService;
        this.bulletinSecretService = bulletinSecretService;
        this.ahttp = ahttp;
        this.settingsService = settingsService;
        this.info = null;
        this.transaction = null;
        this.key = null;
        this.xhr = null;
        this.rid = null;
        this.callbackurl = null;
        this.blockchainurl = null;
        this.bulletin_secret = null;
        this.their_bulletin_secret = null;
        this.shared_secret = null;
        this.to = null;
        this.txnattempts = null;
        this.cbattempts = null;
        this.prevTxn = null;
        this.txns = null;
        this.resolve = null;
        this.unspent_transaction_override = null;
        this.value = null;
        this.username = null;
        this.signatures = null;
    }
    TransactionService.prototype.generateTransaction = function (info) {
        var _this = this;
        return new Promise(function (resolve, reject) {
            _this.key = _this.bulletinSecretService.key;
            _this.bulletin_secret = _this.bulletinSecretService.generate_bulletin_secret();
            _this.username = _this.bulletinSecretService.username;
            _this.txnattempts = [12, 5, 4];
            _this.cbattempts = [12, 5, 4];
            _this.info = info;
            _this.their_bulletin_secret = _this.info.their_bulletin_secret;
            _this.unspent_transaction_override = _this.info.unspent_transaction;
            _this.blockchainurl = _this.info.blockchainurl;
            _this.callbackurl = _this.info.callbackurl;
            _this.to = _this.info.to;
            _this.value = _this.info.value;
            if (_this.info.rid) {
                _this.rid = _this.info.rid;
            }
            else if (_this.info.relationship && _this.info.relationship.their_bulletin_secret) {
                var bulletin_secrets = [_this.bulletin_secret, _this.info.relationship.their_bulletin_secret].sort(function (a, b) {
                    return a.toLowerCase().localeCompare(b.toLowerCase());
                });
                _this.rid = forge.sha256.create().update(bulletin_secrets[0] + bulletin_secrets[1]).digest().toHex();
            }
            else if (_this.info.their_bulletin_secret) {
                bulletin_secrets = [_this.bulletin_secret, _this.info.their_bulletin_secret].sort(function (a, b) {
                    return a.toLowerCase().localeCompare(b.toLowerCase());
                });
                _this.rid = forge.sha256.create().update(bulletin_secrets[0] + bulletin_secrets[1]).digest().toHex();
            }
            else {
                _this.rid = '';
            }
            _this.transaction = {
                rid: _this.rid,
                fee: 0.00,
                requester_rid: typeof _this.info.requester_rid == 'undefined' ? '' : _this.info.requester_rid,
                requested_rid: typeof _this.info.requested_rid == 'undefined' ? '' : _this.info.requested_rid,
                outputs: [],
                time: parseInt(((+new Date()) / 1000).toString()).toString(),
                public_key: _this.key.getPublicKeyBuffer().toString('hex')
            };
            if (_this.info.dh_public_key && _this.info.relationship.dh_private_key) {
                _this.transaction.dh_public_key = _this.info.dh_public_key;
            }
            if (_this.to) {
                _this.transaction.outputs.push({
                    to: _this.to,
                    value: _this.value || 0
                });
            }
            if (_this.transaction.outputs.length > 0) {
                var transaction_total = _this.transaction.outputs[0].value + _this.transaction.fee;
            }
            else {
                transaction_total = _this.transaction.fee;
            }
            if ((_this.info.relationship && _this.info.relationship.dh_private_key && _this.walletService.wallet.balance < (_this.transaction.outputs[0].value + _this.transaction.fee)) /* || this.walletService.wallet.unspent_transactions.length == 0*/) {
                reject("not enough money");
                return;
            }
            else {
                var inputs = [];
                var input_sum = 0;
                var unspent_transactions = void 0;
                if (_this.unspent_transaction_override) {
                    unspent_transactions = [_this.unspent_transaction_override];
                }
                else {
                    _this.info.relationship = _this.info.relationship || {};
                    if (_this.info.requester_rid ||
                        _this.info.requested_rid || // is friend request/accept or group message
                        _this.info.relationship.postText || // is post
                        _this.info.relationship.comment || // is comment
                        _this.info.relationship.react || // is react
                        _this.info.relationship.chatText || // is chat
                        _this.info.relationship.signIn || // is signin
                        (!_this.info.requester_rid && !_this.info.requested_rid && _this.rid) || // is register, we now only allow registration and friend request/accept from non-fastgraph inputs
                        Object.keys(_this.info.relationship).length == 0 // is transfer
                    ) {
                        unspent_transactions = _this.walletService.wallet.txns_for_fastgraph;
                    }
                    else {
                        return reject('either no unspent outputs or wrong transaction type for unspent outputs');
                    }
                    if (unspent_transactions.length == 0 &&
                        _this.info.requester_rid && _this.info.requested_rid &&
                        _this.info.dh_public_key && _this.info.relationship.dh_private_key) { //creating a new relationship is the only txn we allow to come from non-fastgraph
                        unspent_transactions = _this.walletService.wallet.unspent_transactions;
                    }
                    unspent_transactions.sort(function (a, b) {
                        if (a.height < b.height)
                            return -1;
                        if (a.height > b.height)
                            return 1;
                        return 0;
                    });
                }
                dance: for (var i = 0; i < unspent_transactions.length; i++) {
                    var unspent_transaction = unspent_transactions[i];
                    for (var j = 0; j < unspent_transaction.outputs.length; j++) {
                        var unspent_output = unspent_transaction.outputs[j];
                        if (unspent_output.to === _this.key.getAddress()) {
                            inputs.push({ id: unspent_transaction.id });
                            input_sum += parseFloat(unspent_output.value);
                            if (input_sum >= transaction_total) {
                                _this.transaction.outputs.push({
                                    to: _this.key.getAddress(),
                                    value: (input_sum - transaction_total)
                                });
                                break dance;
                            }
                        }
                    }
                }
            }
            var myAddress = _this.key.getAddress();
            var found = false;
            for (var h = 0; h < _this.transaction.outputs.length; h++) {
                if (_this.transaction.outputs[h].to == myAddress) {
                    found = true;
                }
            }
            if (!found) {
                _this.transaction.outputs.push({
                    to: _this.key.getAddress(),
                    value: 0
                });
            }
            if (input_sum < transaction_total) {
                return reject(false);
            }
            _this.transaction.inputs = inputs;
            var inputs_hashes = [];
            for (i = 0; i < inputs.length; i++) {
                inputs_hashes.push(inputs[i].id);
            }
            var inputs_hashes_arr = inputs_hashes.sort(function (a, b) {
                if (a.toLowerCase() < b.toLowerCase())
                    return -1;
                if (a.toLowerCase() > b.toLowerCase())
                    return 1;
                return 0;
            });
            var inputs_hashes_concat = inputs_hashes_arr.join('');
            var outputs_hashes = [];
            for (i = 0; i < _this.transaction.outputs.length; i++) {
                outputs_hashes.push(_this.transaction.outputs[i].to + _this.transaction.outputs[i].value.toFixed(8));
            }
            var outputs_hashes_arr = outputs_hashes.sort(function (a, b) {
                if (a.toLowerCase() < b.toLowerCase())
                    return -1;
                if (a.toLowerCase() > b.toLowerCase())
                    return 1;
                return 0;
            });
            var outputs_hashes_concat = outputs_hashes_arr.join('');
            if (_this.info.relationship) {
                bulletin_secrets = [_this.bulletin_secret, _this.info.relationship.bulletin_secret].sort(function (a, b) {
                    return a.toLowerCase().localeCompare(b.toLowerCase());
                });
                _this.rid = foobar.bitcoin.crypto.sha256(bulletin_secrets[0] + bulletin_secrets[1]).toString('hex');
            }
            else {
                _this.info.relationship = {};
            }
            if (_this.info.dh_public_key && _this.info.relationship.dh_private_key) {
                // creating new relationship
                _this.transaction.relationship = _this.encrypt();
                var hash = foobar.bitcoin.crypto.sha256(_this.transaction.public_key +
                    _this.transaction.time +
                    _this.transaction.dh_public_key +
                    _this.transaction.rid +
                    _this.transaction.relationship +
                    _this.transaction.fee.toFixed(8) +
                    _this.transaction.requester_rid +
                    _this.transaction.requested_rid +
                    inputs_hashes_concat +
                    outputs_hashes_concat).toString('hex');
            }
            else if (typeof _this.info.relationship.groupChatText !== 'undefined') {
                // group chat
                _this.transaction.relationship = _this.shared_encrypt(_this.their_bulletin_secret, JSON.stringify(_this.info.relationship));
                hash = foobar.bitcoin.crypto.sha256(_this.transaction.public_key +
                    _this.transaction.time +
                    _this.transaction.rid +
                    _this.transaction.relationship +
                    _this.transaction.fee.toFixed(8) +
                    _this.transaction.requester_rid +
                    _this.transaction.requested_rid +
                    inputs_hashes_concat +
                    outputs_hashes_concat).toString('hex');
            }
            else if (_this.info.relationship.postText) {
                // group post
                _this.transaction.relationship = _this.shared_encrypt(_this.their_bulletin_secret, JSON.stringify(_this.info.relationship));
                hash = foobar.bitcoin.crypto.sha256(_this.transaction.public_key +
                    _this.transaction.time +
                    _this.transaction.rid +
                    _this.transaction.relationship +
                    _this.transaction.fee.toFixed(8) +
                    _this.transaction.requester_rid +
                    _this.transaction.requested_rid +
                    inputs_hashes_concat +
                    outputs_hashes_concat).toString('hex');
            }
            else if (_this.info.relationship.comment) {
                // group comment
                _this.transaction.relationship = _this.shared_encrypt(_this.their_bulletin_secret, JSON.stringify(_this.info.relationship));
                hash = foobar.bitcoin.crypto.sha256(_this.transaction.public_key +
                    _this.transaction.time +
                    _this.transaction.rid +
                    _this.transaction.relationship +
                    _this.transaction.fee.toFixed(8) +
                    _this.transaction.requester_rid +
                    _this.transaction.requested_rid +
                    inputs_hashes_concat +
                    outputs_hashes_concat).toString('hex');
            }
            else if (_this.info.relationship.react) {
                // group react
                _this.transaction.relationship = _this.shared_encrypt(_this.their_bulletin_secret, JSON.stringify(_this.info.relationship));
                hash = foobar.bitcoin.crypto.sha256(_this.transaction.public_key +
                    _this.transaction.time +
                    _this.transaction.rid +
                    _this.transaction.relationship +
                    _this.transaction.fee.toFixed(8) +
                    _this.transaction.requester_rid +
                    _this.transaction.requested_rid +
                    inputs_hashes_concat +
                    outputs_hashes_concat).toString('hex');
            }
            else if (_this.info.relationship.chatText) {
                // chat
                _this.transaction.relationship = _this.shared_encrypt(_this.info.shared_secret, JSON.stringify(_this.info.relationship));
                hash = foobar.bitcoin.crypto.sha256(_this.transaction.public_key +
                    _this.transaction.time +
                    _this.transaction.rid +
                    _this.transaction.relationship +
                    _this.transaction.fee.toFixed(8) +
                    _this.transaction.requester_rid +
                    _this.transaction.requested_rid +
                    inputs_hashes_concat +
                    outputs_hashes_concat).toString('hex');
            }
            else if (_this.info.relationship.signIn) {
                // sign in
                _this.transaction.relationship = _this.shared_encrypt(_this.info.shared_secret, JSON.stringify(_this.info.relationship));
                hash = foobar.bitcoin.crypto.sha256(_this.transaction.public_key +
                    _this.transaction.time +
                    _this.transaction.rid +
                    _this.transaction.relationship +
                    _this.transaction.fee.toFixed(8) +
                    inputs_hashes_concat +
                    outputs_hashes_concat).toString('hex');
            }
            else {
                //straight transaction
                hash = foobar.bitcoin.crypto.sha256(_this.transaction.public_key +
                    _this.transaction.time +
                    _this.transaction.rid +
                    _this.transaction.fee.toFixed(8) +
                    inputs_hashes_concat +
                    outputs_hashes_concat).toString('hex');
            }
            _this.transaction.hash = hash;
            var attempt = _this.txnattempts.pop();
            attempt = _this.cbattempts.pop();
            _this.transaction.id = _this.get_transaction_id(_this.transaction.hash, attempt);
            if (hash) {
                resolve(hash);
            }
            else {
                reject(false);
            }
        });
    };
    TransactionService.prototype.getFastGraphSignature = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            _this.ahttp.post(_this.settingsService.remoteSettings['baseUrl'] + '/sign-raw-transaction', {
                hash: _this.transaction.hash,
                bulletin_secret: _this.bulletinSecretService.bulletin_secret,
                input: _this.transaction.inputs[0].id,
                id: _this.transaction.id,
                txn: _this.transaction
            })
                .subscribe(function (res) {
                try {
                    var data = res.json();
                    _this.transaction.signatures = [data.signature];
                    resolve();
                }
                catch (err) {
                    reject();
                }
            }, function (err) {
                reject();
            });
        });
    };
    TransactionService.prototype.sendTransaction = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            var url = '';
            if (_this.transaction.signatures && _this.transaction.signatures.length > 0) {
                url = _this.settingsService.remoteSettings['fastgraphUrl'] + '?bulletin_secret=' + _this.bulletin_secret + '&to=' + _this.key.getAddress() + '&username=' + _this.username;
            }
            else {
                url = _this.settingsService.remoteSettings['transactionUrl'] + '?bulletin_secret=' + _this.bulletin_secret + '&to=' + _this.key.getAddress() + '&username=' + _this.username;
            }
            _this.ahttp.post(url, _this.transaction)
                .subscribe(function (data) {
                try {
                    resolve(JSON.parse(data['_body']));
                }
                catch (err) {
                    reject(err);
                }
            }, function (error) {
                if (_this.txnattempts.length > 0) {
                    reject();
                }
            });
        });
    };
    TransactionService.prototype.sendCallback = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            if (_this.callbackurl) {
                _this.ahttp.post(_this.callbackurl, {
                    bulletin_secret: _this.bulletin_secret,
                    to: _this.key.getAddress(),
                    username: _this.username
                })
                    .subscribe(function (data) {
                    resolve(JSON.parse(data['_body']));
                }, function (error) {
                    if (_this.cbattempts.length > 0) {
                        reject();
                    }
                });
            }
        });
    };
    TransactionService.prototype.get_transaction_id = function (hash, trynum) {
        var combine = new Uint8Array(hash.length);
        //combine[0] = 0;
        //combine[1] = 64;
        for (var i = 0; i < hash.length; i++) {
            combine[i] = hash.charCodeAt(i);
        }
        var shaMessage = foobar.bitcoin.crypto.sha256(combine);
        var signature = this.key.sign(shaMessage);
        var der = signature.toDER();
        return foobar.base64.fromByteArray(der);
    };
    TransactionService.prototype.direct_message = function (data) {
        //placeholder
    };
    TransactionService.prototype.hexToBytes = function (s) {
        var arr = [];
        for (var i = 0; i < s.length; i += 2) {
            var c = s.substr(i, 2);
            arr.push(parseInt(c, 16));
        }
        return String.fromCharCode.apply(null, arr);
    };
    TransactionService.prototype.hexToByteArray = function (byteArray) {
        var callback = function (byte) {
            return ('0' + (byte & 0xFF).toString(16)).slice(-2);
        };
        return Array.from(byteArray, callback);
    };
    TransactionService.prototype.byteArrayToHexString = function (byteArray) {
        var callback = function (byte) {
            return ('0' + (byte & 0xFF).toString(16)).slice(-2);
        };
        return Array.from(byteArray, callback).join('');
    };
    TransactionService.prototype.encrypt = function () {
        var key = forge.pkcs5.pbkdf2(forge.sha256.create().update(this.key.toWIF()).digest().toHex(), 'salt', 400, 32);
        var cipher = forge.cipher.createCipher('AES-CBC', key);
        var iv = forge.random.getBytesSync(16);
        cipher.start({ iv: iv });
        cipher.update(forge.util.createBuffer(iv + JSON.stringify(this.info.relationship)));
        cipher.finish();
        return cipher.output.toHex();
    };
    TransactionService.prototype.shared_encrypt = function (shared_secret, message) {
        var key = forge.pkcs5.pbkdf2(forge.sha256.create().update(shared_secret).digest().toHex(), 'salt', 400, 32);
        var cipher = forge.cipher.createCipher('AES-CBC', key);
        var iv = forge.random.getBytesSync(16);
        cipher.start({ iv: iv });
        cipher.update(forge.util.createBuffer(iv + Base64.encode(message)));
        cipher.finish();
        return cipher.output.toHex();
    };
    TransactionService.prototype.decrypt = function (message) {
        var key = forge.pkcs5.pbkdf2(forge.sha256.create().update(this.key.toWIF()).digest().toHex(), 'salt', 400, 32);
        var decipher = forge.cipher.createDecipher('AES-CBC', key);
        var enc = this.hexToBytes(message);
        decipher.start({ iv: enc.slice(0, 16) });
        decipher.update(forge.util.createBuffer(enc.slice(16)));
        decipher.finish();
        return decipher.output;
    };
    TransactionService.prototype.shared_decrypt = function (shared_secret, message) {
        var key = forge.pkcs5.pbkdf2(forge.sha256.create().update(shared_secret).digest().toHex(), 'salt', 400, 32);
        var decipher = forge.cipher.createDecipher('AES-CBC', key);
        var enc = this.hexToBytes(message);
        decipher.start({ iv: enc.slice(0, 16) });
        decipher.update(forge.util.createBuffer(enc.slice(16)));
        decipher.finish();
        return decipher.output;
    };
    TransactionService = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["B" /* Injectable */])(),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_2__wallet_service__["a" /* WalletService */],
            __WEBPACK_IMPORTED_MODULE_1__bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_4__angular_http__["b" /* Http */],
            __WEBPACK_IMPORTED_MODULE_3__settings_service__["a" /* SettingsService */]])
    ], TransactionService);
    return TransactionService;
}());

//# sourceMappingURL=transaction.service.js.map

/***/ }),

/***/ 40:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return GraphService; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__ionic_storage__ = __webpack_require__(33);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__bulletinSecret_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__settings_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__ionic_native_badge__ = __webpack_require__(301);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__angular_http__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6_ionic_angular__ = __webpack_require__(10);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};







var GraphService = /** @class */ (function () {
    function GraphService(storage, bulletinSecretService, settingsService, badge, platform, ahttp) {
        this.storage = storage;
        this.bulletinSecretService = bulletinSecretService;
        this.settingsService = settingsService;
        this.badge = badge;
        this.platform = platform;
        this.ahttp = ahttp;
        this.getGraphError = false;
        this.getSentFriendRequestsError = false;
        this.getGroupsRequestsError = false;
        this.getFriendRequestsError = false;
        this.getFriendsError = false;
        this.getMessagesError = false;
        this.getNewMessagesError = false;
        this.getSignInsError = false;
        this.getNewSignInsError = false;
        this.getPostsError = false;
        this.getReactsError = false;
        this.getCommentsError = false;
        this.getcommentReactsError = false;
        this.getcommentRepliesError = false;
        this.usernames = {};
        this.bulletin_secret = '';
        this.stored_secrets = {};
        this.stored_secrets_by_rid = {};
        this.accepted_friend_requests = [];
        this.keys = {};
        this.new_messages_count = 0;
        this.new_messages_counts = {};
        this.new_group_messages_count = 0;
        this.new_group_messages_counts = {};
        this.new_sign_ins_count = this.new_sign_ins_count || 0;
        this.new_sign_ins_counts = {};
        this.friend_request_count = this.friend_request_count || 0;
        this.usernames = {};
        this.friends_indexed = {};
    }
    GraphService.prototype.endpointRequest = function (endpoint, ids, rids) {
        var _this = this;
        if (ids === void 0) { ids = null; }
        if (rids === void 0) { rids = null; }
        return new Promise(function (resolve, reject) {
            var headers = new __WEBPACK_IMPORTED_MODULE_5__angular_http__["a" /* Headers */]();
            headers.append('Authorization', 'Bearer ' + _this.settingsService.tokens[_this.bulletinSecretService.keyname]);
            var options = new __WEBPACK_IMPORTED_MODULE_5__angular_http__["d" /* RequestOptions */]({ headers: headers, withCredentials: true });
            var promise = null;
            if (ids) {
                promise = _this.ahttp.post(_this.settingsService.remoteSettings['graphUrl'] + '/' + endpoint + '?origin=' + encodeURIComponent(window.location.origin) + '&bulletin_secret=' + _this.bulletinSecretService.bulletin_secret, { ids: ids }, options);
            }
            else if (rids) {
                promise = _this.ahttp.post(_this.settingsService.remoteSettings['graphUrl'] + '/' + endpoint + '?origin=' + encodeURIComponent(window.location.origin) + '&bulletin_secret=' + _this.bulletinSecretService.bulletin_secret, { rids: rids }, options);
            }
            else {
                promise = _this.ahttp.get(_this.settingsService.remoteSettings['graphUrl'] + '/' + endpoint + '?origin=' + encodeURIComponent(window.location.origin) + '&bulletin_secret=' + _this.bulletinSecretService.bulletin_secret, options);
            }
            promise
                .subscribe(function (data) {
                try {
                    var info = JSON.parse(data['_body']);
                    _this.graph.rid = info.rid;
                    _this.graph.bulletin_secret = info.bulletin_secret;
                    _this.graph.registered = info.registered;
                    _this.graph.pending_registration = info.pending_registration;
                    resolve(info);
                }
                catch (err) {
                }
            }, function (err) {
                reject(err);
            });
        });
    };
    GraphService.prototype.getInfo = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            if (!_this.settingsService.remoteSettings['walletUrl'])
                return resolve();
            _this.endpointRequest('get-graph-info')
                .then(function (data) {
                _this.getGraphError = false;
                resolve(data);
            }).catch(function (err) {
                _this.getGraphError = true;
                reject(null);
            });
        });
    };
    GraphService.prototype.getSentFriendRequests = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            _this.endpointRequest('get-graph-sent-friend-requests')
                .then(function (data) {
                _this.graph.sent_friend_requests = _this.parseSentFriendRequests(data.sent_friend_requests);
                _this.getSentFriendRequestsError = false;
                resolve();
            }).catch(function (err) {
                _this.getSentFriendRequestsError = true;
                reject(null);
            });
        });
    };
    GraphService.prototype.getFriendRequests = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            _this.endpointRequest('get-graph-friend-requests')
                .then(function (data) {
                _this.graph.friend_requests = _this.parseFriendRequests(data.friend_requests);
                _this.getFriendRequestsError = false;
                resolve();
            }).catch(function (err) {
                _this.getFriendRequestsError = true;
                reject(null);
            }).catch(function () {
                reject();
            });
        });
    };
    GraphService.prototype.getFriends = function () {
        var _this = this;
        return this.getSentFriendRequests()
            .then(function () {
            return _this.getFriendRequests();
        })
            .then(function () {
            return _this.endpointRequest('get-graph-friends');
        })
            .then(function (data) {
            return _this.parseFriends(data.friends);
        })
            .then(function (friends) {
            //sort list alphabetically by username
            friends.sort(function (a, b) {
                if (a.username < b.username)
                    return -1;
                if (a.username > b.username)
                    return 1;
                return 0;
            });
            _this.graph.friends = friends;
        });
    };
    GraphService.prototype.getGroups = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            _this.endpointRequest('get-graph-sent-friend-requests')
                .then(function (data) {
                return _this.parseGroups(data.sent_friend_requests);
            }).then(function (groups) {
                _this.getGroupsRequestsError = false;
                _this.graph.groups = groups;
                resolve();
            }).catch(function (err) {
                _this.getGroupsRequestsError = true;
                reject(null);
            });
        });
    };
    GraphService.prototype.getMessages = function (rid) {
        var _this = this;
        //get messages for a specific friend
        return new Promise(function (resolve, reject) {
            _this.endpointRequest('get-graph-messages', null, [rid])
                .then(function (data) {
                return _this.parseMessages(data.messages, 'new_messages_counts', 'new_messages_count', rid, 'chatText', 'last_message_height');
            })
                .then(function (chats) {
                if (!_this.graph.messages) {
                    _this.graph.messages = {};
                }
                if (chats[rid]) {
                    _this.graph.messages[rid] = chats[rid];
                    _this.graph.messages[rid].sort(function (a, b) {
                        if (parseInt(a.time) > parseInt(b.time))
                            return 1;
                        if (parseInt(a.time) < parseInt(b.time))
                            return -1;
                        return 0;
                    });
                }
                _this.getMessagesError = false;
                return resolve(chats[rid]);
            }).catch(function (err) {
                _this.getMessagesError = true;
                reject(err);
            });
        });
    };
    GraphService.prototype.getNewMessages = function () {
        var _this = this;
        //get the latest message for each friend
        return new Promise(function (resolve, reject) {
            _this.endpointRequest('get-graph-new-messages')
                .then(function (data) {
                return _this.parseNewMessages(data.new_messages, 'new_messages_counts', 'new_messages_count', 'last_message_height');
            })
                .then(function (newChats) {
                _this.graph.newMessages = newChats;
                _this.getNewMessagesError = false;
                resolve(newChats);
            }).catch(function (err) {
                _this.getNewMessagesError = true;
                reject(err);
            });
        });
    };
    GraphService.prototype.getGroupMessages = function (key, requested_rid, rid) {
        var _this = this;
        //get messages for a specific friend
        var choice_rid = requested_rid || rid;
        return new Promise(function (resolve, reject) {
            _this.endpointRequest('get-graph-messages', null, [choice_rid])
                .then(function (data) {
                return _this.parseGroupMessages(key, data.messages, 'new_group_messages_counts', 'new_group_messages_count', rid, ['groupChatText', 'groupChatFileName'], 'last_group_message_height');
            })
                .then(function (chats) {
                if (!_this.graph.messages) {
                    _this.graph.messages = {};
                }
                if (choice_rid && chats[choice_rid]) {
                    _this.graph.messages[choice_rid] = chats[choice_rid];
                    _this.graph.messages[choice_rid].sort(function (a, b) {
                        if (parseInt(a.time) > parseInt(b.time))
                            return 1;
                        if (parseInt(a.time) < parseInt(b.time))
                            return -1;
                        return 0;
                    });
                }
                _this.getMessagesError = false;
                return resolve(chats[choice_rid]);
            }).catch(function (err) {
                _this.getMessagesError = true;
                reject(err);
            });
        });
    };
    GraphService.prototype.getNewGroupMessages = function () {
        var _this = this;
        //get the latest message for each friend
        return new Promise(function (resolve, reject) {
            _this.endpointRequest('get-graph-new-messages')
                .then(function (data) {
                return _this.parseNewMessages(data.new_messages, 'new_group_messages_counts', 'new_group_messages_count', 'last_group_message_height');
            })
                .then(function (newChats) {
                _this.graph.newGroupMessages = newChats;
                _this.getNewMessagesError = false;
                resolve(newChats);
            }).catch(function (err) {
                _this.getNewMessagesError = true;
                reject(err);
            });
        });
    };
    GraphService.prototype.getSignIns = function (rid) {
        var _this = this;
        //get sign ins for a specific friend
        return new Promise(function (resolve, reject) {
            _this.endpointRequest('get-graph-new-messages')
                .then(function (data) {
                return _this.parseMessages(data.new_messages, 'new_sign_ins_counts', 'new_sign_ins_count', rid, 'signIn', 'last_sign_in_height');
            })
                .then(function (signIns) {
                signIns[rid].sort(function (a, b) {
                    if (a.height > b.height)
                        return -1;
                    if (a.height < b.height)
                        return 1;
                    return 0;
                });
                _this.graph.signIns = signIns[rid];
                _this.getSignInsError = false;
                resolve(signIns[rid]);
            }).catch(function (err) {
                _this.getSignInsError = true;
                reject(err);
            });
        });
    };
    GraphService.prototype.getNewSignIns = function () {
        var _this = this;
        //get the latest sign ins for a specific friend
        return new Promise(function (resolve, reject) {
            _this.endpointRequest('get-graph-new-messages')
                .then(function (data) {
                return _this.parseNewMessages(data.new_messages, 'new_sign_ins_counts', 'new_sign_ins_count', 'last_sign_in_height');
            })
                .then(function (newSignIns) {
                _this.graph.newSignIns = newSignIns;
                _this.getNewSignInsError = false;
                resolve(newSignIns);
            }).catch(function (err) {
                _this.getNewSignInsError = true;
                reject(err);
            });
        });
    };
    GraphService.prototype.getReacts = function (ids, rid) {
        var _this = this;
        if (rid === void 0) { rid = null; }
        return new Promise(function (resolve, reject) {
            _this.endpointRequest('get-graph-reacts', ids)
                .then(function (data) {
                _this.graph.reacts = _this.parseMessages(data.reacts, 'new_reacts_counts', 'new_reacts_count', rid, 'chatText', 'last_react_height');
                _this.getReactsError = false;
                resolve(data.reacts);
            }).catch(function () {
                _this.getReactsError = true;
                reject(null);
            });
        });
    };
    GraphService.prototype.getComments = function (ids, rid) {
        var _this = this;
        if (rid === void 0) { rid = null; }
        return new Promise(function (resolve, reject) {
            _this.endpointRequest('get-graph-comments', ids)
                .then(function (data) {
                _this.graph.comments = _this.parseMessages(data.reacts, 'new_comments_counts', 'new_comments_count', rid, 'chatText', 'last_comment_height');
                _this.getCommentsError = false;
                resolve(data.comments);
            }).catch(function () {
                _this.getCommentsError = true;
                reject(null);
            });
        });
    };
    GraphService.prototype.getCommentReacts = function (ids, rid) {
        var _this = this;
        if (rid === void 0) { rid = null; }
        return new Promise(function (resolve, reject) {
            _this.endpointRequest('get-graph-reacts', ids)
                .then(function (data) {
                _this.graph.commentReacts = _this.parseMessages(data.reacts, 'new_comment_reacts_counts', 'new_comment_reacts_count', rid, 'chatText', 'last_comment_react_height');
                _this.getcommentReactsError = false;
                resolve(data.comment_reacts);
            }).catch(function () {
                _this.getcommentReactsError = true;
                reject(null);
            });
        });
    };
    GraphService.prototype.getCommentReplies = function (ids, rid) {
        var _this = this;
        if (rid === void 0) { rid = null; }
        return new Promise(function (resolve, reject) {
            _this.endpointRequest('get-graph-comments', ids)
                .then(function (data) {
                _this.graph.commentReplies = _this.parseMessages(data.reacts, 'new_comment_comments_counts', 'new_comment_comments_count', rid, 'chatText', 'last_comment_comment_height');
                _this.getcommentRepliesError = false;
                resolve(data.comments);
            }).catch(function () {
                _this.getcommentRepliesError = true;
                reject(null);
            });
        });
    };
    GraphService.prototype.parseSentFriendRequests = function (sent_friend_requests) {
        var sent_friend_requestsObj = {};
        var sent_friend_request;
        if (!this.graph.friends)
            this.graph.friends = [];
        for (var i = 0; i < sent_friend_requests.length; i++) {
            sent_friend_request = sent_friend_requests[i];
            if (!this.keys[sent_friend_request.rid]) {
                this.keys[sent_friend_request.rid] = {
                    dh_private_keys: [],
                    dh_public_keys: []
                };
            }
            var decrypted = this.decrypt(sent_friend_request['relationship']);
            try {
                var relationship = JSON.parse(decrypted);
                if (!relationship.their_username || !relationship.their_bulletin_secret)
                    continue;
                sent_friend_requestsObj[sent_friend_request.rid] = sent_friend_request;
                //not sure how this affects the friends list yet, since we can't return friends from here
                //friends[sent_friend_request.rid] = sent_friend_request;
                sent_friend_request['relationship'] = relationship;
                this.friends_indexed[sent_friend_request.rid] = sent_friend_request;
                if (this.keys[sent_friend_request.rid].dh_private_keys.indexOf(relationship.dh_private_key) === -1 && relationship.dh_private_key) {
                    this.keys[sent_friend_request.rid].dh_private_keys.push(relationship.dh_private_key);
                }
            }
            catch (err) {
                if (this.keys[sent_friend_request.rid].dh_public_keys.indexOf(sent_friend_request.dh_public_key) === -1 && sent_friend_request.dh_public_key) {
                    this.keys[sent_friend_request.rid].dh_public_keys.push(sent_friend_request.dh_public_key);
                }
            }
        }
        for (var j = 0; j < sent_friend_requests.length; j++) {
            sent_friend_request = sent_friend_requests[j];
            if (typeof (sent_friend_request['relationship']) != 'object') {
                //TODO: VERIFY THE BULLETIN SECRET!
                if (sent_friend_requestsObj[sent_friend_request.rid]) {
                    this.graph.friends.push(sent_friend_requestsObj[sent_friend_request.rid]);
                    delete sent_friend_requestsObj[sent_friend_request.rid];
                }
            }
        }
        var arr_sent_friend_requests = [];
        for (var i_1 in sent_friend_requestsObj) {
            arr_sent_friend_requests.push(sent_friend_requestsObj[i_1].rid);
            if (sent_friend_requestsObj[i_1].relationship && sent_friend_requestsObj[i_1].relationship.their_username) {
                this.usernames[sent_friend_requestsObj[i_1].rid] = sent_friend_requestsObj[i_1].their_username;
            }
        }
        var sent_friend_requests_diff = new Set(arr_sent_friend_requests);
        sent_friend_requests = [];
        var arr_sent_friend_request_keys = Array.from(sent_friend_requests_diff.keys());
        for (i = 0; i < arr_sent_friend_request_keys.length; i++) {
            sent_friend_requests.push(sent_friend_requestsObj[arr_sent_friend_request_keys[i]]);
        }
        return sent_friend_requests;
    };
    GraphService.prototype.parseFriendRequests = function (friend_requests) {
        var friend_requestsObj = {};
        if (!this.graph.friends)
            this.graph.friends = [];
        for (var i = 0; i < friend_requests.length; i++) {
            var friend_request = friend_requests[i];
            if (!this.keys[friend_request.rid]) {
                this.keys[friend_request.rid] = {
                    dh_private_keys: [],
                    dh_public_keys: []
                };
            }
            var decrypted = this.decrypt(friend_request.relationship);
            try {
                var relationship = JSON.parse(decrypted);
                this.graph.friends.push(friend_request);
                delete friend_requestsObj[friend_request.rid];
                friend_request['relationship'] = relationship;
                this.friends_indexed[friend_request.rid] = friend_request;
                if (this.keys[friend_request.rid].dh_private_keys.indexOf(relationship.dh_private_key) === -1 && relationship.dh_private_key) {
                    this.keys[friend_request.rid].dh_private_keys.push(relationship.dh_private_key);
                }
            }
            catch (err) {
                friend_requestsObj[friend_request.rid] = friend_request;
                if (this.keys[friend_request.rid].dh_public_keys.indexOf(friend_request.dh_public_key) === -1 && friend_request.dh_public_key) {
                    this.keys[friend_request.rid].dh_public_keys.push(friend_request.dh_public_key);
                }
            }
        }
        var arr_friend_requests = [];
        for (var i_2 in friend_requestsObj) {
            arr_friend_requests.push(friend_requestsObj[i_2].rid);
            if (friend_requestsObj[i_2].relationship && friend_requestsObj[i_2].relationship.their_username) {
                this.usernames[friend_requestsObj[i_2].rid] = friend_requestsObj[i_2].their_username;
            }
        }
        friend_requests = [];
        var friend_requests_diff = new Set(arr_friend_requests);
        if (arr_friend_requests.length > 0) {
            var arr_friend_request_keys = Array.from(friend_requests_diff.keys());
            for (i = 0; i < arr_friend_request_keys.length; i++) {
                friend_requests.push(friend_requestsObj[arr_friend_request_keys[i]]);
            }
        }
        this.friend_request_count = friend_requests.length;
        if (this.platform.is('android') || this.platform.is('ios')) {
            this.badge.set(friend_requests.length);
        }
        return friend_requests;
    };
    GraphService.prototype.parseFriends = function (friends) {
        var _this = this;
        // we must call getSentFriendRequests and getFriendRequests before getting here
        // because we need this.keys to be populated with the dh_public_keys and dh_private_keys from the requests
        // though friends really should be cached
        // should be key: shared-secret_rid|pub_key[:26]priv_key[:26], value: {shared_secret: <shared_secret>, friend: [transaction.dh_public_key, transaction.dh_private_key]}
        return new Promise(function (resolve, reject) {
            //start "just do dedup yada server because yada server adds itself to the friends array automatically straight from the api"
            var friendsObj = {};
            if (!_this.graph.friends)
                _this.graph.friends = [];
            friends = friends.concat(_this.graph.friends);
            for (var i = 0; i < friends.length; i++) {
                var friend = friends[i];
                if (!_this.keys[friend.rid]) {
                    _this.keys[friend.rid] = {
                        dh_private_keys: [],
                        dh_public_keys: []
                    };
                }
                var decrypted;
                var bypassDecrypt = false;
                if (typeof friend.relationship == 'object') {
                    bypassDecrypt = true;
                }
                else {
                    decrypted = _this.decrypt(friend.relationship);
                }
                try {
                    var relationship;
                    if (!bypassDecrypt) {
                        relationship = JSON.parse(decrypted);
                        friend['relationship'] = relationship;
                    }
                    friendsObj[friend.rid] = friend;
                    if (_this.keys[friend.rid].dh_private_keys.indexOf(relationship.dh_private_key) === -1 && relationship.dh_private_key) {
                        _this.keys[friend.rid].dh_private_keys.push(relationship.dh_private_key);
                    }
                }
                catch (err) {
                    if (_this.keys[friend.rid].dh_public_keys.indexOf(friend.dh_public_key) === -1 && friend.dh_public_key) {
                        _this.keys[friend.rid].dh_public_keys.push(friend.dh_public_key);
                    }
                }
            }
            var secrets_rids = [];
            var stored_secrets_keys = Object.keys(_this.stored_secrets);
            for (i = 0; i < stored_secrets_keys.length; i++) {
                var rid = stored_secrets_keys[i].slice('shared_secret-'.length, stored_secrets_keys[i].indexOf('|'));
                secrets_rids.push(rid);
            }
            for (i = 0; i < _this.graph.sent_friend_requests.length; i++) {
                var sent_friend_request = _this.graph.sent_friend_requests[i];
                if (secrets_rids.indexOf(sent_friend_request.rid) >= 0) {
                    friendsObj[sent_friend_request.rid] = sent_friend_request;
                }
            }
            for (i = 0; i < _this.graph.friend_requests.length; i++) {
                var friend_request = _this.graph.friend_requests[i];
                if (secrets_rids.indexOf(friend_request.rid) >= 0) {
                    friendsObj[friend_request.rid] = friend_request;
                }
            }
            var arr_friends = Object.keys(friendsObj);
            friends = [];
            var friends_diff = new Set(arr_friends);
            if (arr_friends.length > 0) {
                var arr_friends_keys = Array.from(friends_diff.keys());
                for (i = 0; i < arr_friends_keys.length; i++) {
                    friends.push(friendsObj[arr_friends_keys[i]]);
                    if (friendsObj[arr_friends_keys[i]].relationship && friendsObj[arr_friends_keys[i]].relationship.their_username) {
                        _this.usernames[friendsObj[arr_friends_keys[i]].rid] = friendsObj[arr_friends_keys[i]].their_username;
                    }
                    if (friendsObj[arr_friends_keys[i]].username) {
                        _this.usernames[friendsObj[arr_friends_keys[i]].rid] = friendsObj[arr_friends_keys[i]].username;
                    }
                }
            }
            resolve(friends);
        });
    };
    GraphService.prototype.parseGroups = function (groups) {
        var _this = this;
        // we must call getSentFriendRequests and getFriendRequests before getting here
        // because we need this.keys to be populated with the dh_public_keys and dh_private_keys from the requests
        // though friends really should be cached
        // should be key: shared-secret_rid|pub_key[:26]priv_key[:26], value: {shared_secret: <shared_secret>, friend: [transaction.dh_public_key, transaction.dh_private_key]}
        return new Promise(function (resolve, reject) {
            //start "just do dedup yada server because yada server adds itself to the friends array automatically straight from the api"
            var groupsObj = {};
            if (!_this.graph.groups)
                _this.graph.groups = [];
            for (var i = 0; i < groups.length; i++) {
                var group = groups[i];
                if (!_this.keys[group.rid]) {
                    _this.keys[group.rid] = {
                        dh_private_keys: [],
                        dh_public_keys: []
                    };
                }
                var decrypted;
                var bypassDecrypt = false;
                if (typeof group.relationship == 'object') {
                    bypassDecrypt = true;
                }
                else {
                    decrypted = _this.decrypt(group.relationship);
                }
                try {
                    var relationship;
                    if (!bypassDecrypt) {
                        relationship = JSON.parse(decrypted);
                        group['relationship'] = relationship;
                    }
                    if (!group.relationship.group) {
                        continue;
                    }
                    groupsObj[group.rid] = group;
                    if (_this.keys[group.rid].dh_private_keys.indexOf(relationship.dh_private_key) === -1 && relationship.dh_private_key) {
                        _this.keys[group.rid].dh_private_keys.push(relationship.dh_private_key);
                    }
                }
                catch (err) {
                    if (_this.keys[group.rid].dh_public_keys.indexOf(group.dh_public_key) === -1 && group.dh_public_key) {
                        _this.keys[group.rid].dh_public_keys.push(group.dh_public_key);
                    }
                }
            }
            var arr_friends = Object.keys(groupsObj);
            groups = [];
            var friends_diff = new Set(arr_friends);
            if (arr_friends.length > 0) {
                var arr_friends_keys = Array.from(friends_diff.keys());
                for (i = 0; i < arr_friends_keys.length; i++) {
                    groups.push(groupsObj[arr_friends_keys[i]]);
                    if (groupsObj[arr_friends_keys[i]].relationship && groupsObj[arr_friends_keys[i]].relationship.their_username) {
                        _this.usernames[groupsObj[arr_friends_keys[i]].rid] = groupsObj[arr_friends_keys[i]].relationship.their_username;
                    }
                    if (groupsObj[arr_friends_keys[i]].username) {
                        _this.usernames[groupsObj[arr_friends_keys[i]].rid] = groupsObj[arr_friends_keys[i]].username;
                    }
                }
            }
            resolve(groups);
            return groups;
        });
    };
    GraphService.prototype.parseMessages = function (messages, graphCounts, graphCount, rid, messageType, messageHeightType) {
        var _this = this;
        if (rid === void 0) { rid = null; }
        if (messageType === void 0) { messageType = null; }
        if (messageHeightType === void 0) { messageHeightType = null; }
        this[graphCount] = 0;
        return new Promise(function (resolve, reject) {
            _this.getSharedSecrets().then(function () {
                return _this.getMessageHeights(graphCounts, messageHeightType);
            })
                .then(function () {
                var chats = {};
                dance: for (var i = 0; i < messages.length; i++) {
                    var message = messages[i];
                    if (!rid && chats[message.rid])
                        continue;
                    if (rid && message.rid !== rid)
                        continue;
                    if (!message.rid)
                        continue;
                    if (!_this.stored_secrets[message.rid])
                        continue;
                    if (message.dh_public_key)
                        continue;
                    //hopefully we've prepared the stored_secrets option before getting here 
                    //by calling getSentFriendRequests and getFriendRequests
                    for (var j = 0; j < _this.stored_secrets[message.rid].length; j++) {
                        var shared_secret = _this.stored_secrets[message.rid][j];
                        try {
                            var decrypted = _this.shared_decrypt(shared_secret.shared_secret, message.relationship);
                        }
                        catch (error) {
                            continue;
                        }
                        try {
                            var messageJson = JSON.parse(decrypted);
                        }
                        catch (err) {
                            continue;
                        }
                        if (messageJson[messageType]) {
                            message.relationship = messageJson;
                            message.shared_secret = shared_secret.shared_secret;
                            message.dh_public_key = shared_secret.dh_public_key;
                            message.dh_private_key = shared_secret.dh_private_key;
                            message.username = _this.usernames[message.rid];
                            messages[message.rid] = message;
                            if (!chats[message.rid]) {
                                chats[message.rid] = [];
                            }
                            try {
                                message.relationship.chatText = JSON.parse(Base64.decode(messageJson[messageType]));
                                message.relationship.isInvite = true;
                            }
                            catch (err) {
                                //not an invite, do nothing
                            }
                            chats[message.rid].push(message);
                            if (_this[graphCounts][message.rid]) {
                                if (message.height > _this[graphCounts][message.rid]) {
                                    _this[graphCount]++;
                                    if (!_this[graphCounts][message.rid]) {
                                        _this[graphCounts][message.rid] = 0;
                                    }
                                    _this[graphCounts][message.rid]++;
                                }
                            }
                            else {
                                _this[graphCounts][message.rid] = 1;
                                _this[graphCount]++;
                            }
                        }
                        continue dance;
                    }
                }
                resolve(chats);
            });
        });
    };
    GraphService.prototype.parseNewMessages = function (messages, graphCounts, graphCount, heightType) {
        var _this = this;
        this[graphCount] = 0;
        this[graphCounts] = {};
        var my_public_key = this.bulletinSecretService.key.getPublicKeyBuffer().toString('hex');
        return new Promise(function (resolve, reject) {
            return _this.getMessageHeights(graphCounts, heightType)
                .then(function () {
                var new_messages = [];
                for (var i = 0; i < messages.length; i++) {
                    var message = messages[i];
                    message.username = _this.usernames[message.rid];
                    if (message.public_key != my_public_key) {
                        if (_this[graphCounts][message.rid]) {
                            if (parseInt(message.time) > _this[graphCounts][message.rid]) {
                                _this[graphCounts][message.rid] = message.time;
                                _this[graphCount]++;
                            }
                        }
                        else {
                            _this[graphCounts][message.rid] = parseInt(message.time);
                            _this[graphCount]++;
                        }
                        new_messages.push(message);
                    }
                }
                return resolve(new_messages);
            });
        });
    };
    GraphService.prototype.parseGroupMessages = function (key, messages, graphCounts, graphCount, rid, messageType, messageHeightType) {
        var _this = this;
        if (rid === void 0) { rid = null; }
        if (messageType === void 0) { messageType = null; }
        if (messageHeightType === void 0) { messageHeightType = null; }
        this[graphCount] = 0;
        return new Promise(function (resolve, reject) {
            _this.getGroupMessageHeights(graphCounts, messageHeightType)
                .then(function () {
                var chats = {};
                for (var i = 0; i < messages.length; i++) {
                    var message = messages[i];
                    //hopefully we've prepared the stored_secrets option before getting here 
                    //by calling getSentFriendRequests and getFriendRequests
                    try {
                        var decrypted = _this.shared_decrypt(key, message.relationship);
                        console.log(decrypted);
                    }
                    catch (error) {
                        continue;
                    }
                    try {
                        var messageJson = JSON.parse(decrypted);
                    }
                    catch (err) {
                        continue;
                    }
                    var group_message_rid = message.requested_rid || message.rid;
                    if (messageJson[messageType[0]] || messageJson[messageType[1]]) {
                        message.relationship = messageJson;
                        message.username = _this.usernames[group_message_rid];
                        messages[group_message_rid] = message;
                        if (!chats[group_message_rid]) {
                            chats[group_message_rid] = [];
                        }
                        chats[group_message_rid].push(message);
                        if (_this[graphCounts][group_message_rid]) {
                            if (message.height > _this[graphCounts][group_message_rid]) {
                                _this[graphCount]++;
                                if (!_this[graphCounts][group_message_rid]) {
                                    _this[graphCounts][group_message_rid] = 0;
                                }
                                _this[graphCounts][group_message_rid]++;
                            }
                        }
                        else {
                            _this[graphCounts][group_message_rid] = 1;
                            _this[graphCount]++;
                        }
                    }
                }
                resolve(chats);
            });
        });
    };
    GraphService.prototype.getSharedSecrets = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            _this.getFriends()
                .then(function () {
                for (var i in _this.keys) {
                    if (!_this.stored_secrets[i]) {
                        _this.stored_secrets[i] = [];
                    }
                    var stored_secrets_by_dh_public_key = {};
                    for (var ss = 0; ss < _this.stored_secrets[i].length; ss++) {
                        stored_secrets_by_dh_public_key[_this.stored_secrets[i][ss].dh_public_key + _this.stored_secrets[i][ss].dh_private_key] = _this.stored_secrets[i][ss];
                    }
                    for (var j = 0; j < _this.keys[i].dh_private_keys.length; j++) {
                        var dh_private_key = _this.keys[i].dh_private_keys[j];
                        if (!dh_private_key)
                            continue;
                        for (var k = 0; k < _this.keys[i].dh_public_keys.length; k++) {
                            var dh_public_key = _this.keys[i].dh_public_keys[k];
                            if (!dh_public_key)
                                continue;
                            if (stored_secrets_by_dh_public_key[dh_public_key + dh_private_key]) {
                                continue;
                            }
                            var privk = new Uint8Array(dh_private_key.match(/[\da-f]{2}/gi).map(function (h) {
                                return parseInt(h, 16);
                            }));
                            var pubk = new Uint8Array(dh_public_key.match(/[\da-f]{2}/gi).map(function (h) {
                                return parseInt(h, 16);
                            }));
                            var shared_secret = _this.toHex(X25519.getSharedKey(privk, pubk));
                            _this.stored_secrets[i].push({
                                shared_secret: shared_secret,
                                dh_public_key: dh_public_key,
                                dh_private_key: dh_private_key,
                                rid: i
                            });
                        }
                    }
                }
                resolve();
            });
        });
    };
    GraphService.prototype.getSharedSecretForRid = function (rid) {
        var _this = this;
        return new Promise(function (resolve, reject) {
            _this.getSharedSecrets()
                .then(function () {
                if (_this.stored_secrets[rid] && _this.stored_secrets[rid].length > 0) {
                    resolve(_this.stored_secrets[rid][0]);
                }
                else {
                    reject('no shared secret found for rid: ' + rid);
                }
            });
        });
    };
    GraphService.prototype.getMessageHeights = function (graphCounts, heightType) {
        var _this = this;
        this[graphCounts] = {};
        return new Promise(function (resolve, reject) {
            _this.storage.forEach(function (value, key) {
                if (key.indexOf(heightType) === 0) {
                    var rid = key.slice(heightType + '-'.length);
                    _this[graphCounts][rid] = parseInt(value);
                }
            })
                .then(function () {
                resolve();
            });
        });
    };
    GraphService.prototype.getGroupMessageHeights = function (graphCounts, heightType) {
        var _this = this;
        this[graphCounts] = {};
        return new Promise(function (resolve, reject) {
            _this.storage.forEach(function (value, key) {
                if (key.indexOf(heightType) === 0) {
                    var rid = key.slice(heightType + '-'.length);
                    _this[graphCounts][rid] = parseInt(value);
                }
            })
                .then(function () {
                resolve();
            });
        });
    };
    GraphService.prototype.decrypt = function (message) {
        var key = forge.pkcs5.pbkdf2(forge.sha256.create().update(this.bulletinSecretService.key.toWIF()).digest().toHex(), 'salt', 400, 32);
        var decipher = forge.cipher.createDecipher('AES-CBC', key);
        var enc = this.hexToBytes(message);
        decipher.start({ iv: enc.slice(0, 16) });
        decipher.update(forge.util.createBuffer(enc.slice(16)));
        decipher.finish();
        return decipher.output.data;
    };
    GraphService.prototype.shared_decrypt = function (shared_secret, message) {
        var key = forge.pkcs5.pbkdf2(forge.sha256.create().update(shared_secret).digest().toHex(), 'salt', 400, 32);
        var decipher = forge.cipher.createDecipher('AES-CBC', key);
        var enc = this.hexToBytes(message);
        decipher.start({ iv: enc.slice(0, 16) });
        decipher.update(forge.util.createBuffer(enc.slice(16)));
        decipher.finish();
        return Base64.decode(decipher.output.data);
    };
    GraphService.prototype.hexToByteArray = function (str) {
        if (!str) {
            return new Uint8Array([]);
        }
        var a = [];
        for (var i = 0, len = str.length; i < len; i += 2) {
            a.push(parseInt(str.substr(i, 2), 16));
        }
        return new Uint8Array(a);
    };
    GraphService.prototype.hexToBytes = function (s) {
        var arr = [];
        for (var i = 0; i < s.length; i += 2) {
            var c = s.substr(i, 2);
            arr.push(parseInt(c, 16));
        }
        return String.fromCharCode.apply(null, arr);
    };
    GraphService.prototype.toHex = function (byteArray) {
        var callback = function (byte) {
            return ('0' + (byte & 0xFF).toString(16)).slice(-2);
        };
        return Array.from(byteArray, callback).join('');
    };
    GraphService = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["B" /* Injectable */])(),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1__ionic_storage__["b" /* Storage */],
            __WEBPACK_IMPORTED_MODULE_2__bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_3__settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_4__ionic_native_badge__["a" /* Badge */],
            __WEBPACK_IMPORTED_MODULE_6_ionic_angular__["k" /* Platform */],
            __WEBPACK_IMPORTED_MODULE_5__angular_http__["b" /* Http */]])
    ], GraphService);
    return GraphService;
}());

//# sourceMappingURL=graph.service.js.map

/***/ }),

/***/ 437:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return AppModule; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_platform_browser__ = __webpack_require__(46);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2_ionic_angular__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__angular_http__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__angular_common__ = __webpack_require__(42);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_component__ = __webpack_require__(479);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__pages_home_home__ = __webpack_require__(180);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__pages_home_postmodal__ = __webpack_require__(302);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__pages_list_list__ = __webpack_require__(51);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__pages_settings_settings__ = __webpack_require__(305);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_10__pages_chat_chat__ = __webpack_require__(182);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_11__pages_profile_profile__ = __webpack_require__(86);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_12__pages_group_group__ = __webpack_require__(183);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_13__pages_siafiles_siafiles__ = __webpack_require__(184);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_14__pages_stream_stream__ = __webpack_require__(306);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_15__ionic_native_status_bar__ = __webpack_require__(298);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_16__ionic_native_splash_screen__ = __webpack_require__(300);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_17__ionic_native_qr_scanner__ = __webpack_require__(308);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_18_ngx_qrcode2__ = __webpack_require__(492);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_19__ionic_storage__ = __webpack_require__(33);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_20__graph_service__ = __webpack_require__(40);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_21__bulletinSecret_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_22__peer_service__ = __webpack_require__(181);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_23__settings_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_24__wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_25__transaction_service__ = __webpack_require__(34);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_26__opengraphparser_service__ = __webpack_require__(109);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_27__firebase_service__ = __webpack_require__(185);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_28__pages_sendreceive_sendreceive__ = __webpack_require__(307);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_29__ionic_native_clipboard__ = __webpack_require__(512);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_30__ionic_native_social_sharing__ = __webpack_require__(85);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_31__ionic_native_badge__ = __webpack_require__(301);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_32__ionic_native_deeplinks__ = __webpack_require__(513);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_33__ionic_native_firebase__ = __webpack_require__(303);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_34__ionic_tools_emoji_picker__ = __webpack_require__(514);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_35__ionic_native_file__ = __webpack_require__(562);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_36_ionic2_auto_complete__ = __webpack_require__(563);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_37__autocomplete_provider__ = __webpack_require__(304);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};






































var AppModule = /** @class */ (function () {
    function AppModule() {
    }
    AppModule = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_1__angular_core__["L" /* NgModule */])({
            declarations: [
                __WEBPACK_IMPORTED_MODULE_5__app_component__["a" /* MyApp */],
                __WEBPACK_IMPORTED_MODULE_6__pages_home_home__["a" /* HomePage */],
                __WEBPACK_IMPORTED_MODULE_7__pages_home_postmodal__["a" /* PostModal */],
                __WEBPACK_IMPORTED_MODULE_8__pages_list_list__["a" /* ListPage */],
                __WEBPACK_IMPORTED_MODULE_9__pages_settings_settings__["a" /* Settings */],
                __WEBPACK_IMPORTED_MODULE_28__pages_sendreceive_sendreceive__["a" /* SendReceive */],
                __WEBPACK_IMPORTED_MODULE_10__pages_chat_chat__["a" /* ChatPage */],
                __WEBPACK_IMPORTED_MODULE_11__pages_profile_profile__["a" /* ProfilePage */],
                __WEBPACK_IMPORTED_MODULE_12__pages_group_group__["a" /* GroupPage */],
                __WEBPACK_IMPORTED_MODULE_13__pages_siafiles_siafiles__["a" /* SiaFiles */],
                __WEBPACK_IMPORTED_MODULE_14__pages_stream_stream__["a" /* StreamPage */]
            ],
            imports: [
                __WEBPACK_IMPORTED_MODULE_0__angular_platform_browser__["a" /* BrowserModule */],
                __WEBPACK_IMPORTED_MODULE_36_ionic2_auto_complete__["b" /* AutoCompleteModule */],
                __WEBPACK_IMPORTED_MODULE_2_ionic_angular__["e" /* IonicModule */].forRoot(__WEBPACK_IMPORTED_MODULE_5__app_component__["a" /* MyApp */], {}, {
                    links: []
                }),
                __WEBPACK_IMPORTED_MODULE_19__ionic_storage__["a" /* IonicStorageModule */].forRoot({
                    name: '__mydb',
                    driverOrder: ['sqlite', 'websql', 'indexeddb']
                }),
                __WEBPACK_IMPORTED_MODULE_18_ngx_qrcode2__["a" /* NgxQRCodeModule */],
                __WEBPACK_IMPORTED_MODULE_3__angular_http__["c" /* HttpModule */],
                __WEBPACK_IMPORTED_MODULE_34__ionic_tools_emoji_picker__["a" /* EmojiPickerModule */].forRoot(),
                __WEBPACK_IMPORTED_MODULE_4__angular_common__["b" /* CommonModule */]
            ],
            bootstrap: [__WEBPACK_IMPORTED_MODULE_2_ionic_angular__["c" /* IonicApp */]],
            entryComponents: [
                __WEBPACK_IMPORTED_MODULE_5__app_component__["a" /* MyApp */],
                __WEBPACK_IMPORTED_MODULE_6__pages_home_home__["a" /* HomePage */],
                __WEBPACK_IMPORTED_MODULE_7__pages_home_postmodal__["a" /* PostModal */],
                __WEBPACK_IMPORTED_MODULE_8__pages_list_list__["a" /* ListPage */],
                __WEBPACK_IMPORTED_MODULE_9__pages_settings_settings__["a" /* Settings */],
                __WEBPACK_IMPORTED_MODULE_28__pages_sendreceive_sendreceive__["a" /* SendReceive */],
                __WEBPACK_IMPORTED_MODULE_10__pages_chat_chat__["a" /* ChatPage */],
                __WEBPACK_IMPORTED_MODULE_11__pages_profile_profile__["a" /* ProfilePage */],
                __WEBPACK_IMPORTED_MODULE_12__pages_group_group__["a" /* GroupPage */],
                __WEBPACK_IMPORTED_MODULE_13__pages_siafiles_siafiles__["a" /* SiaFiles */],
                __WEBPACK_IMPORTED_MODULE_14__pages_stream_stream__["a" /* StreamPage */]
            ],
            providers: [
                __WEBPACK_IMPORTED_MODULE_15__ionic_native_status_bar__["a" /* StatusBar */],
                __WEBPACK_IMPORTED_MODULE_16__ionic_native_splash_screen__["a" /* SplashScreen */],
                { provide: __WEBPACK_IMPORTED_MODULE_1__angular_core__["v" /* ErrorHandler */], useClass: __WEBPACK_IMPORTED_MODULE_2_ionic_angular__["d" /* IonicErrorHandler */] },
                __WEBPACK_IMPORTED_MODULE_17__ionic_native_qr_scanner__["a" /* QRScanner */],
                __WEBPACK_IMPORTED_MODULE_18_ngx_qrcode2__["a" /* NgxQRCodeModule */],
                __WEBPACK_IMPORTED_MODULE_20__graph_service__["a" /* GraphService */],
                __WEBPACK_IMPORTED_MODULE_21__bulletinSecret_service__["a" /* BulletinSecretService */],
                __WEBPACK_IMPORTED_MODULE_22__peer_service__["a" /* PeerService */],
                __WEBPACK_IMPORTED_MODULE_23__settings_service__["a" /* SettingsService */],
                __WEBPACK_IMPORTED_MODULE_24__wallet_service__["a" /* WalletService */],
                __WEBPACK_IMPORTED_MODULE_25__transaction_service__["a" /* TransactionService */],
                __WEBPACK_IMPORTED_MODULE_26__opengraphparser_service__["a" /* OpenGraphParserService */],
                __WEBPACK_IMPORTED_MODULE_29__ionic_native_clipboard__["a" /* Clipboard */],
                __WEBPACK_IMPORTED_MODULE_30__ionic_native_social_sharing__["a" /* SocialSharing */],
                __WEBPACK_IMPORTED_MODULE_31__ionic_native_badge__["a" /* Badge */],
                __WEBPACK_IMPORTED_MODULE_32__ionic_native_deeplinks__["a" /* Deeplinks */],
                __WEBPACK_IMPORTED_MODULE_33__ionic_native_firebase__["a" /* Firebase */],
                __WEBPACK_IMPORTED_MODULE_27__firebase_service__["a" /* FirebaseService */],
                __WEBPACK_IMPORTED_MODULE_35__ionic_native_file__["a" /* File */],
                __WEBPACK_IMPORTED_MODULE_37__autocomplete_provider__["a" /* CompleteTestService */],
                __WEBPACK_IMPORTED_MODULE_36_ionic2_auto_complete__["a" /* AutoCompleteComponent */]
            ]
        })
    ], AppModule);
    return AppModule;
}());

//# sourceMappingURL=app.module.js.map

/***/ }),

/***/ 479:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return MyApp; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__ionic_native_status_bar__ = __webpack_require__(298);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__ionic_native_splash_screen__ = __webpack_require__(300);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__graph_service__ = __webpack_require__(40);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__settings_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__bulletinSecret_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__pages_home_home__ = __webpack_require__(180);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__pages_list_list__ = __webpack_require__(51);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_10__pages_settings_settings__ = __webpack_require__(305);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_11__pages_siafiles_siafiles__ = __webpack_require__(184);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_12__pages_stream_stream__ = __webpack_require__(306);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_13__pages_sendreceive_sendreceive__ = __webpack_require__(307);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};















var MyApp = /** @class */ (function () {
    function MyApp(platform, statusBar, splashScreen, walletService, graphService, settingsService, bulletinSecretService, events) {
        var _this = this;
        this.platform = platform;
        this.statusBar = statusBar;
        this.splashScreen = splashScreen;
        this.walletService = walletService;
        this.graphService = graphService;
        this.settingsService = settingsService;
        this.bulletinSecretService = bulletinSecretService;
        this.events = events;
        events.subscribe('graph', function () {
            _this.rootPage = __WEBPACK_IMPORTED_MODULE_8__pages_home_home__["a" /* HomePage */];
        });
        events.subscribe('pages-error', function () {
        });
        this.graphService.graph = {
            comments: "",
            reacts: "",
            commentReacts: ""
        };
        this.initializeApp();
        this.walletService.get().then(function (data) {
            _this.rootPage = __WEBPACK_IMPORTED_MODULE_10__pages_settings_settings__["a" /* Settings */];
        }).catch(function () {
            _this.rootPage = __WEBPACK_IMPORTED_MODULE_10__pages_settings_settings__["a" /* Settings */];
        });
        this.pages = [
            { title: 'Home', label: 'Dashboard', component: __WEBPACK_IMPORTED_MODULE_8__pages_home_home__["a" /* HomePage */], count: false, color: '' },
            { title: 'Stream', label: 'Stream', component: __WEBPACK_IMPORTED_MODULE_12__pages_stream_stream__["a" /* StreamPage */], count: false, color: '' },
            { title: 'Groups', label: 'Groups', component: __WEBPACK_IMPORTED_MODULE_9__pages_list_list__["a" /* ListPage */], count: false, color: '' },
            { title: 'Files', label: 'Files', component: __WEBPACK_IMPORTED_MODULE_11__pages_siafiles_siafiles__["a" /* SiaFiles */], count: false, color: '' },
            { title: 'Friends', label: 'Friends', component: __WEBPACK_IMPORTED_MODULE_9__pages_list_list__["a" /* ListPage */], count: false, color: '' },
            { title: 'Messages', label: 'Messages', component: __WEBPACK_IMPORTED_MODULE_9__pages_list_list__["a" /* ListPage */], count: false, color: '' },
            { title: 'Friend Requests', label: 'Friend Requests', component: __WEBPACK_IMPORTED_MODULE_9__pages_list_list__["a" /* ListPage */], count: false, color: '' },
            { title: 'Sent Requests', label: 'Sent Requests', component: __WEBPACK_IMPORTED_MODULE_9__pages_list_list__["a" /* ListPage */], count: false, color: '' },
            { title: 'Send / Receive', label: 'Send / Receive', component: __WEBPACK_IMPORTED_MODULE_13__pages_sendreceive_sendreceive__["a" /* SendReceive */], count: false, color: '' },
            { title: 'Identity', label: 'Identity', component: __WEBPACK_IMPORTED_MODULE_10__pages_settings_settings__["a" /* Settings */], count: false, color: '' }
        ];
    }
    MyApp.prototype.initializeApp = function () {
        var _this = this;
        this.platform.ready().then(function () {
            // Okay, so the platform is ready and our plugins are available.
            // Here you can do any higher level native things you might need.
            if (_this.platform.is('android') || _this.platform.is('ios')) {
                _this.statusBar.styleDefault();
                _this.splashScreen.hide();
            }
        });
    };
    MyApp.prototype.openPage = function (page) {
        // Reset the content nav to have just this page
        // we wouldn't want the back button to show in this scenario
        this.nav.setRoot(page.component, { pageTitle: page });
    };
    MyApp.prototype.decrypt = function (message) {
        var key = forge.pkcs5.pbkdf2(forge.sha256.create().update(this.bulletinSecretService.key.toWIF()).digest().toHex(), 'salt', 400, 32);
        var decipher = forge.cipher.createDecipher('AES-CBC', key);
        var enc = this.hexToBytes(message);
        decipher.start({ iv: enc.slice(0, 16) });
        decipher.update(forge.util.createBuffer(enc.slice(16)));
        decipher.finish();
        return decipher.output;
    };
    MyApp.prototype.hexToBytes = function (s) {
        var arr = [];
        for (var i = 0; i < s.length; i += 2) {
            var c = s.substr(i, 2);
            arr.push(parseInt(c, 16));
        }
        return String.fromCharCode.apply(null, arr);
    };
    __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["_14" /* ViewChild */])(__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["h" /* Nav */]),
        __metadata("design:type", __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["h" /* Nav */])
    ], MyApp.prototype, "nav", void 0);
    MyApp = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["n" /* Component */])({template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/app/app.html"*/'<ion-split-pane>\n  <ion-menu [content]="content">\n    <ion-header>\n      <ion-toolbar>\n        <ion-title>\n          <img src="assets/img/yadacoinlogotextsmall.png" class="logotext">\n          <ion-note style="font-size: 12px">\n            v1.3\n          </ion-note>\n        </ion-title>\n      </ion-toolbar>\n    </ion-header>\n\n    <ion-content>\n      <ion-list *ngIf="bulletinSecretService.key">\n        <ng-container *ngFor="let p of pages">\n          <button \n            menuClose \n            ion-item \n            (click)="openPage(p)"\n            [color]="graphService.friend_request_count > 0 ? \'primary\' : \'grey\'"\n            *ngIf="p.title == \'Friend Requests\'"\n          >\n            {{p.label}}\n          </button>\n          <button \n            menuClose \n            ion-item \n            (click)="openPage(p)"\n            [color]="graphService.new_messages_count > 0 ? \'primary\' : \'grey\'"\n            *ngIf="p.title == \'Messages\'"\n          >\n            {{p.label}}\n          </button>\n          <button \n            menuClose \n            ion-item \n            (click)="openPage(p)"\n            *ngIf="[\'Messages\', \'Friend Requests\'].indexOf(p.title) < 0"\n          >\n            {{p.label}}\n          </button>\n        </ng-container>\n      </ion-list>\n      <img src="assets/img/yadacoinlogosmall.png" class="logo">\n    </ion-content>\n\n  </ion-menu>\n  <!-- Disable swipe-to-go-back because it\'s poor UX to combine STGB with side menus -->\n  <ion-nav [root]="rootPage" main #content swipeBackEnabled="false"></ion-nav>\n</ion-split-pane>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/app/app.html"*/
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["k" /* Platform */],
            __WEBPACK_IMPORTED_MODULE_2__ionic_native_status_bar__["a" /* StatusBar */],
            __WEBPACK_IMPORTED_MODULE_3__ionic_native_splash_screen__["a" /* SplashScreen */],
            __WEBPACK_IMPORTED_MODULE_7__wallet_service__["a" /* WalletService */],
            __WEBPACK_IMPORTED_MODULE_4__graph_service__["a" /* GraphService */],
            __WEBPACK_IMPORTED_MODULE_5__settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_6__bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["b" /* Events */]])
    ], MyApp);
    return MyApp;
}());

//# sourceMappingURL=app.component.js.map

/***/ }),

/***/ 51:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return ListPage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__ionic_storage__ = __webpack_require__(33);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_graph_service__ = __webpack_require__(40);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_bulletinSecret_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_transaction_service__ = __webpack_require__(34);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__app_settings_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__ionic_native_social_sharing__ = __webpack_require__(85);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__chat_chat__ = __webpack_require__(182);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_10__group_group__ = __webpack_require__(183);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_11__profile_profile__ = __webpack_require__(86);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_12__angular_http__ = __webpack_require__(18);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};















var ListPage = /** @class */ (function () {
    function ListPage(navCtrl, navParams, storage, graphService, bulletinSecretService, walletService, transactionService, socialSharing, alertCtrl, loadingCtrl, events, ahttp, settingsService) {
        this.navCtrl = navCtrl;
        this.navParams = navParams;
        this.storage = storage;
        this.graphService = graphService;
        this.bulletinSecretService = bulletinSecretService;
        this.walletService = walletService;
        this.transactionService = transactionService;
        this.socialSharing = socialSharing;
        this.alertCtrl = alertCtrl;
        this.loadingCtrl = loadingCtrl;
        this.events = events;
        this.ahttp = ahttp;
        this.settingsService = settingsService;
        this.loadingModal = this.loadingCtrl.create({
            content: 'Please wait...'
        });
        this.refresh(null)
            .catch(function () {
            console.log('error refreshing listpage');
        });
    }
    ListPage_1 = ListPage;
    ListPage.prototype.refresh = function (refresher) {
        var _this = this;
        return this.walletService.get()
            .then(function () {
            _this.loading = true;
            _this.loadingBalance = true;
            // If we navigated to this page, we will have an item available as a nav param
            return _this.storage.get('blockchainAddress');
        })
            .then(function (blockchainAddress) {
            _this.blockchainAddress = blockchainAddress;
            return _this.storage.get('baseUrl');
        })
            .then(function (baseUrl) {
            _this.baseUrl = baseUrl;
            _this.selectedItem = _this.navParams.get('item');
            _this.context = _this.navParams.get('context');
            _this.pageTitle = _this.selectedItem ? _this.selectedItem.pageTitle : _this.navParams.get('pageTitle').title;
            return _this.choosePage();
        })
            .then(function () {
            if (refresher)
                refresher.complete();
        }).catch(function () {
            console.log('listpage walletService error');
        });
    };
    ListPage.prototype.choosePage = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            if (!_this.selectedItem) {
                _this.label = _this.navParams.get('pageTitle').label;
                // Let's populate this page with some filler content for funzies
                _this.icons = ['flask', 'wifi', 'beer', 'football', 'basketball', 'paper-plane',
                    'american-football', 'boat', 'bluetooth', 'build'];
                var my_public_key = '';
                var graphArray = [];
                if (_this.pageTitle == 'Friends') {
                    return _this.graphService.getFriends()
                        .then(function () {
                        var graphArray = _this.graphService.graph.friends;
                        graphArray = _this.getDistinctFriends(graphArray).friend_list;
                        graphArray.sort(function (a, b) {
                            if (a.relationship.their_username.toLowerCase() < b.relationship.their_username.toLowerCase())
                                return -1;
                            if (a.relationship.their_username.toLowerCase() > b.relationship.their_username.toLowerCase())
                                return 1;
                            return 0;
                        });
                        _this.makeList(graphArray);
                        _this.loading = false;
                    }).catch(function (err) {
                        console.log('listpage getFriends error: ' + err);
                    });
                }
                else if (_this.pageTitle == 'Groups') {
                    my_public_key = _this.bulletinSecretService.key.getPublicKeyBuffer().toString('hex');
                    return _this.graphService.getGroups()
                        .then(function () {
                        return _this.graphService.getNewGroupMessages();
                    })
                        .then(function (graphArray) {
                        var messages = _this.markNew(my_public_key, graphArray, _this.graphService.new_group_messages_counts);
                        var groupsWithMessagesList = _this.getDistinctGroups(messages);
                        _this.populateRemainingGroups(groupsWithMessagesList.group_list, groupsWithMessagesList.used_rids);
                        _this.loading = false;
                        groupsWithMessagesList.group_list.sort(function (a, b) {
                            if (a.relationship.their_username.toLowerCase() < b.relationship.their_username.toLowerCase())
                                return -1;
                            if (a.relationship.their_username.toLowerCase() > b.relationship.their_username.toLowerCase())
                                return 1;
                            return 0;
                        });
                        return _this.makeList(groupsWithMessagesList.group_list);
                    }).catch(function (err) {
                        console.log(err);
                    });
                }
                else if (_this.pageTitle == 'Messages') {
                    my_public_key = _this.bulletinSecretService.key.getPublicKeyBuffer().toString('hex');
                    return _this.graphService.getFriends()
                        .then(function () {
                        return _this.graphService.getNewMessages();
                    })
                        .then(function (graphArray) {
                        var messages = _this.markNew(my_public_key, graphArray, _this.graphService.new_messages_counts);
                        var friendsWithMessagesList = _this.getDistinctFriends(messages);
                        _this.populateRemainingFriends(friendsWithMessagesList.friend_list, friendsWithMessagesList.used_rids);
                        _this.loading = false;
                        friendsWithMessagesList.friend_list.sort(function (a, b) {
                            if (a.relationship.their_username.toLowerCase() < b.relationship.their_username.toLowerCase())
                                return -1;
                            if (a.relationship.their_username.toLowerCase() > b.relationship.their_username.toLowerCase())
                                return 1;
                            return 0;
                        });
                        return _this.makeList(friendsWithMessagesList.friend_list);
                    }).catch(function (err) {
                        console.log(err);
                    });
                }
                else if (_this.pageTitle == 'Sign Ins') {
                    my_public_key = _this.bulletinSecretService.key.getPublicKeyBuffer().toString('hex');
                    return _this.graphService.getFriends()
                        .then(function () {
                        return _this.graphService.getNewSignIns();
                    })
                        .then(function (graphArray) {
                        var sign_ins = _this.markNew(my_public_key, graphArray, _this.graphService.new_sign_ins_counts);
                        var friendsWithSignInsList = _this.getDistinctFriends(sign_ins);
                        _this.populateRemainingFriends(friendsWithSignInsList.friend_list, friendsWithSignInsList.used_rids);
                        _this.loading = false;
                        return _this.makeList(friendsWithSignInsList.friend_list);
                    }).catch(function () {
                        console.log('listpage getFriends or getNewSignIns error');
                    });
                }
                else if (_this.pageTitle == 'Friend Requests') {
                    return _this.graphService.getFriendRequests()
                        .then(function () {
                        var graphArray = _this.graphService.graph.friend_requests;
                        graphArray.sort(function (a, b) {
                            if (a.username.toLowerCase() < b.username.toLowerCase())
                                return -1;
                            if (a.username.toLowerCase() > b.username.toLowerCase())
                                return 1;
                            return 0;
                        });
                        _this.loading = false;
                        return _this.makeList(graphArray);
                    }).catch(function () {
                        console.log('listpage getFriendRequests error');
                    });
                }
                else if (_this.pageTitle == 'Sent Requests') {
                    return _this.graphService.getSentFriendRequests()
                        .then(function () {
                        var graphArray = _this.graphService.graph.sent_friend_requests;
                        graphArray.sort(function (a, b) {
                            if (a.username.toLowerCase() < b.username.toLowerCase())
                                return -1;
                            if (a.username.toLowerCase() > b.username.toLowerCase())
                                return 1;
                            return 0;
                        });
                        _this.loading = false;
                        return _this.makeList(graphArray);
                    }).catch(function () {
                        console.log('listpage getSentFriendRequests error');
                    });
                }
                else if (_this.pageTitle == 'Reacts Detail') {
                    graphArray = _this.navParams.get('detail');
                    _this.loading = false;
                    return _this.makeList(graphArray);
                }
                else if (_this.pageTitle == 'Comment Reacts Detail') {
                    graphArray = _this.navParams.get('detail');
                    _this.loading = false;
                    return _this.makeList(graphArray);
                }
            }
            else {
                _this.loading = false;
                _this.loadingBalance = false;
                if (_this.pageTitle == 'Sent Requests') {
                    resolve();
                }
                else if (_this.pageTitle == 'Friend Requests') {
                    _this.friend_request = _this.navParams.get('item').transaction;
                    resolve();
                }
                else if (_this.pageTitle == 'Sign Ins') {
                    _this.rid = _this.navParams.get('item').transaction.rid;
                    _this.graphService.getSignIns(_this.rid)
                        .then(function (signIn) {
                        _this.signIn = signIn[0];
                        _this.signInText = _this.signIn.relationship.signIn;
                        resolve();
                    }).catch(function () {
                        console.log('listpage getSignIns error');
                        reject();
                    });
                }
            }
        });
    };
    ListPage.prototype.markNew = function (my_public_key, graphArray, graphCount) {
        var collection = [];
        for (var i in graphArray) {
            if (my_public_key !== graphArray[i]['public_key'] && graphCount[i] && graphCount[i] < graphArray[i]['height']) {
                graphArray[i]['new'] = true;
            }
            collection.push(graphArray[i]);
        }
        return collection;
    };
    ListPage.prototype.getDistinctFriends = function (collection) {
        // using the rids from new items
        // make a list of friends sorted by block height descending (most recent)
        var friend_list = [];
        var used_rids = [];
        for (var i = 0; i < collection.length; i++) {
            // we could have multiple transactions per friendship
            // so make sure we're going using the rid once
            var item = collection[i];
            if (!item.relationship || !item.relationship.their_username) {
                continue;
            }
            if (used_rids.indexOf(item.rid) === -1) {
                friend_list.push(item);
                used_rids.push(item.rid);
            }
        }
        return {
            friend_list: friend_list,
            used_rids: used_rids
        };
    };
    ListPage.prototype.getDistinctGroups = function (collection) {
        // using the rids from new items
        // make a list of friends sorted by block height descending (most recent)
        var group_list = [];
        var used_rids = [];
        for (var i = 0; i < collection.length; i++) {
            // we could have multiple transactions per friendship
            // so make sure we're going using the rid once
            var item = collection[i];
            if (!item.relationship || !item.relationship.their_username) {
                continue;
            }
            if (used_rids.indexOf(item.rid) === -1) {
                group_list.push(item);
                used_rids.push(item.rid);
            }
        }
        return {
            group_list: group_list,
            used_rids: used_rids
        };
    };
    ListPage.prototype.populateRemainingFriends = function (friend_list, used_rids) {
        // now add everyone else
        for (var i = 0; i < this.graphService.graph.friends.length; i++) {
            if (used_rids.indexOf(this.graphService.graph.friends[i].rid) === -1) {
                friend_list.push(this.graphService.graph.friends[i]);
                used_rids.push(this.graphService.graph.friends[i].rid);
            }
        }
    };
    ListPage.prototype.populateRemainingGroups = function (friend_list, used_rids) {
        // now add everyone else
        for (var i = 0; i < this.graphService.graph.groups.length; i++) {
            if (used_rids.indexOf(this.graphService.graph.groups[i].rid) === -1) {
                friend_list.push(this.graphService.graph.groups[i]);
                used_rids.push(this.graphService.graph.groups[i].rid);
            }
        }
    };
    ListPage.prototype.makeList = function (graphArray) {
        var _this = this;
        return new Promise(function (resolve, reject) {
            _this.items = [];
            for (var i = 0; i < graphArray.length; i++) {
                _this.items.push({
                    pageTitle: _this.pageTitle,
                    transaction: graphArray[i]
                });
            }
            resolve();
        });
    };
    ListPage.prototype.newChat = function () {
        var item = { pageTitle: { title: "Friends" }, context: 'newChat' };
        this.navCtrl.push(ListPage_1, item);
    };
    ListPage.prototype.itemTapped = function (event, item) {
        if (this.pageTitle == 'Messages') {
            this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_9__chat_chat__["a" /* ChatPage */], {
                item: item
            });
        }
        else if (this.pageTitle == 'Groups') {
            this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_10__group_group__["a" /* GroupPage */], {
                item: item
            });
        }
        else if (this.pageTitle == 'Friends') {
            this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_11__profile_profile__["a" /* ProfilePage */], {
                item: item.transaction
            });
        }
        else {
            this.navCtrl.push(ListPage_1, {
                item: item
            });
        }
    };
    ListPage.prototype.accept = function () {
        var _this = this;
        var alert = this.alertCtrl.create();
        alert.setTitle('Approve Transaction');
        alert.setSubTitle('You are about to spend 1.01 coins.');
        alert.addButton({
            text: 'Cancel',
            handler: function (data) {
                alert.dismiss();
            }
        });
        alert.addButton({
            text: 'Confirm',
            handler: function (data) {
                _this.ahttp.get(_this.settingsService.remoteSettings['baseUrl'] + '/ns?requester_rid=' + _this.friend_request.requester_rid + '&bulletin_secret=' + _this.bulletinSecretService.bulletin_secret)
                    .subscribe(function (res) {
                    var info = res.json();
                    // camera permission was granted
                    var requester_rid = info.requester_rid;
                    var requested_rid = info.requested_rid;
                    if (requester_rid && requested_rid) {
                        // get rid from bulletin secrets
                    }
                    else {
                        requester_rid = '';
                        requested_rid = '';
                    }
                    //////////////////////////////////////////////////////////////////////////
                    // create and send transaction to create the relationship on the blockchain
                    //////////////////////////////////////////////////////////////////////////
                    _this.walletService.get().then(function () {
                        var raw_dh_private_key = window.crypto.getRandomValues(new Uint8Array(32));
                        var raw_dh_public_key = X25519.getPublic(raw_dh_private_key);
                        var dh_private_key = _this.toHex(raw_dh_private_key);
                        var dh_public_key = _this.toHex(raw_dh_public_key);
                        info.dh_private_key = dh_private_key;
                        info.dh_public_key = dh_public_key;
                        return _this.transactionService.generateTransaction({
                            relationship: {
                                dh_private_key: info.dh_private_key,
                                their_bulletin_secret: info.bulletin_secret,
                                their_username: info.username,
                                my_bulletin_secret: _this.bulletinSecretService.generate_bulletin_secret(),
                                my_username: _this.bulletinSecretService.username
                            },
                            dh_public_key: info.dh_public_key,
                            requested_rid: info.requested_rid,
                            requester_rid: info.requester_rid,
                            to: info.to
                        });
                    }).then(function (txn) {
                        return _this.transactionService.sendTransaction();
                    }).then(function (txn) {
                        var alert = _this.alertCtrl.create();
                        alert.setTitle('Friend Accept Sent');
                        alert.setSubTitle('Your Friend Request acceptance has been submitted successfully.');
                        alert.addButton('Ok');
                        alert.present();
                        _this.refresh(null).then(function () {
                            _this.navCtrl.pop();
                        });
                    }).catch(function (err) {
                        console.log(err);
                    });
                }, function (err) {
                    //this.loadingModal2.dismiss();
                    console.log(err);
                });
            }
        });
        alert.present();
    };
    ListPage.prototype.sendSignIn = function () {
        var _this = this;
        var alert = this.alertCtrl.create();
        alert.setTitle('Approve transaction');
        alert.setSubTitle('You are about to spend 0.01 coins ( 0.01 fee)');
        alert.addButton('Cancel');
        alert.addButton({
            text: 'Confirm',
            handler: function (data) {
                _this.walletService.get().then(function () {
                    return _this.graphService.getSharedSecretForRid(_this.rid);
                }).then(function (result) {
                    if (result) {
                        var alert_1 = _this.alertCtrl.create();
                        alert_1.setTitle('Message sent');
                        alert_1.setSubTitle('Your message has been sent successfully');
                        alert_1.addButton('Ok');
                        alert_1.present();
                    }
                    _this.navCtrl.pop();
                });
            }
        });
        alert.present();
    };
    ListPage.prototype.share = function (code) {
        this.socialSharing.share(code);
    };
    ListPage.prototype.showChat = function () {
        var item = { pageTitle: { title: "Chat" } };
        this.navCtrl.push(ListPage_1, item);
    };
    ListPage.prototype.showFriendRequests = function () {
        var item = { pageTitle: { title: "Friend Requests" } };
        this.navCtrl.push(ListPage_1, item);
    };
    ListPage.prototype.toHex = function (byteArray) {
        var callback = function (byte) {
            return ('0' + (byte & 0xFF).toString(16)).slice(-2);
        };
        return Array.from(byteArray, callback).join('');
    };
    var ListPage_1;
    ListPage = ListPage_1 = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["n" /* Component */])({
            selector: 'page-list',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/list/list.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n    <ion-title>{{label}}</ion-title>\n  </ion-navbar>\n</ion-header>\n\n<ion-content>\n  <ion-refresher (ionRefresh)="refresh($event)">\n    <ion-refresher-content></ion-refresher-content>\n  </ion-refresher>\n  <ion-spinner *ngIf="loading"></ion-spinner>\n  <ion-card *ngIf="items && items.length == 0">\n      <ion-card-content>\n        <ion-card-title style="text-overflow:ellipsis;" text-wrap>\n          No items to display.\n      </ion-card-title>\n    </ion-card-content>\n  </ion-card>\n  <ion-list>\n    <button ion-item *ngFor="let item of items" (click)="itemTapped($event, item)">\n      <span *ngIf="pageTitle ==\'Groups\'">{{item.transaction.relationship.their_username}} - <ion-note color="{{item.transaction.pending ? \'danger\' : \'secondary\'}}">{{item.transaction.pending ? \'Not yet saved on blockchain\' : \'Saved on blockchain\'}}</ion-note></span>\n      <span *ngIf="pageTitle ==\'Sent Requests\'">{{item.transaction.relationship.their_username}} - <ion-note color="{{item.transaction.pending ? \'danger\' : \'secondary\'}}">{{item.transaction.pending ? \'Not yet saved on blockchain\' : \'Saved on blockchain\'}}</ion-note></span>\n      <span *ngIf="pageTitle ==\'Friend Requests\'">{{item.transaction.username}} - <ion-note color="{{item.transaction.pending ? \'danger\' : \'secondary\'}}">{{item.transaction.pending ? \'Not yet saved on blockchain\' : \'Saved on blockchain\'}}</ion-note></span>\n      <span *ngIf="pageTitle ==\'Messages\' && !item.transaction.new">{{item.transaction.relationship.their_username}} - <ion-note color="{{item.transaction.pending ? \'danger\' : \'secondary\'}}">{{item.transaction.pending ? \'Not yet saved on blockchain\' : \'Saved on blockchain\'}}</ion-note></span>\n      <span *ngIf="pageTitle ==\'Chat\' && item.transaction.new"><strong>{{item.transaction.relationship.their_username}}</strong></span>\n      <span *ngIf="pageTitle ==\'Sign Ins\' && !item.transaction.new">{{item.transaction.relationship.their_username}}</span>\n      <span *ngIf="pageTitle ==\'Sign Ins\' && item.transaction.new"><strong>{{item.transaction.relationship.their_username}}</strong></span>\n      <span *ngIf="pageTitle ==\'Friends\'">{{item.transaction.relationship.their_username}} - <ion-note color="{{item.transaction.pending ? \'danger\' : \'secondary\'}}">{{item.transaction.pending ? \'Not yet saved on blockchain\' : \'Saved on blockchain\'}}</ion-note></span>\n      <span *ngIf="pageTitle ==\'Reacts Detail\'">{{item.transaction.relationship.react}} {{item.transaction.username}}</span>\n      <span *ngIf="pageTitle ==\'Comment Reacts Detail\'">{{item.transaction.relationship.react}} {{item.transaction.username}}</span>\n    </button>\n  </ion-list>\n  <div *ngIf="selectedItem && pageTitle ==\'Sent Requests\'" padding>\n  </div>\n  <div *ngIf="selectedItem && pageTitle ==\'Friend Requests\'" padding>\n\n    <ion-card *ngIf="friend_request">\n      <ion-card-header>\n        <p><strong>New friend request from {{friend_request.username}}</strong> </p>\n      </ion-card-header>\n      <ion-card-content>\n        <p>{{friend_request.username}} would like to be your friend!</p>\n        <button ion-button secondary (click)="accept()">Accept</button>\n      </ion-card-content>\n    </ion-card>\n    <!-- for now, we can\'t do p2p on WKWebView\n    <button *ngIf="pageTitle == \'Friend Requests\'" ion-button secondary (click)="accept(selectedItem.transaction)">Accept Request</button>\n\n    <button *ngIf="pageTitle == \'Friend Requests\'" ion-button secondary (click)="send_receipt(selectedItem.transaction)">Send Receipt</button>\n    -->\n  </div>\n  <div *ngIf="selectedItem && pageTitle ==\'Friends\'" padding>\n    You navigated here from <b>{{selectedItem.transaction.rid}}</b>\n  </div>\n  <div *ngIf="selectedItem && pageTitle ==\'Posts\'" padding>\n    <a href="{{selectedItem.transaction.relationship.postText}}" target="_blank">{{selectedItem.transaction.relationship.postText}}</a>\n  </div>\n  <div *ngIf="selectedItem && pageTitle ==\'Sign Ins\'" padding>\n\n    <ion-card>\n      <ion-card-header>\n        <p><strong>{{selectedItem.transaction.username}}</strong> has sent you an authorization offer. Accept offer with the \'Sign in\' button.</p>\n      </ion-card-header>\n      <ion-card-content>\n        <button ion-button secondary (click)="sendSignIn()">Sign in</button>\n        Sign in code: {{signInText}}\n      </ion-card-content>\n    </ion-card>\n    <!-- for now, we can\'t do p2p on WKWebView\n    <button *ngIf="pageTitle == \'Friend Requests\'" ion-button secondary (click)="accept(selectedItem.transaction)">Accept Request</button>\n\n    <button *ngIf="pageTitle == \'Friend Requests\'" ion-button secondary (click)="send_receipt(selectedItem.transaction)">Send Receipt</button>\n    -->\n  </div>\n</ion-content>\n'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/list/list.html"*/
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["i" /* NavController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["j" /* NavParams */],
            __WEBPACK_IMPORTED_MODULE_2__ionic_storage__["b" /* Storage */],
            __WEBPACK_IMPORTED_MODULE_3__app_graph_service__["a" /* GraphService */],
            __WEBPACK_IMPORTED_MODULE_4__app_bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_5__app_wallet_service__["a" /* WalletService */],
            __WEBPACK_IMPORTED_MODULE_6__app_transaction_service__["a" /* TransactionService */],
            __WEBPACK_IMPORTED_MODULE_8__ionic_native_social_sharing__["a" /* SocialSharing */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["a" /* AlertController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["f" /* LoadingController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["b" /* Events */],
            __WEBPACK_IMPORTED_MODULE_12__angular_http__["b" /* Http */],
            __WEBPACK_IMPORTED_MODULE_7__app_settings_service__["a" /* SettingsService */]])
    ], ListPage);
    return ListPage;
}());

//# sourceMappingURL=list.js.map

/***/ }),

/***/ 86:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return ProfilePage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__ionic_storage__ = __webpack_require__(33);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_graph_service__ = __webpack_require__(40);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_bulletinSecret_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_transaction_service__ = __webpack_require__(34);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__list_list__ = __webpack_require__(51);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__chat_chat__ = __webpack_require__(182);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__group_group__ = __webpack_require__(183);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_10__angular_http__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_11__app_settings_service__ = __webpack_require__(16);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};














var ProfilePage = /** @class */ (function () {
    function ProfilePage(navCtrl, navParams, storage, walletService, graphService, bulletinSecretService, ahttp, loadingCtrl, settingsService, alertCtrl, transactionService, toastCtrl, events) {
        this.navCtrl = navCtrl;
        this.navParams = navParams;
        this.storage = storage;
        this.walletService = walletService;
        this.graphService = graphService;
        this.bulletinSecretService = bulletinSecretService;
        this.ahttp = ahttp;
        this.loadingCtrl = loadingCtrl;
        this.settingsService = settingsService;
        this.alertCtrl = alertCtrl;
        this.transactionService = transactionService;
        this.toastCtrl = toastCtrl;
        this.events = events;
        this.item = this.navParams.get('item');
        this.refresh(null);
    }
    ProfilePage.prototype.refresh = function (refresher) {
        var _this = this;
        this.isFriend = null;
        this.graphService.getFriends()
            .then(function () {
            for (var i = 0; i < _this.graphService.graph.friends.length; i++) {
                var friend = _this.graphService.graph.friends[i];
                if (friend.rid === _this.item.rid || friend.rid === _this.item.requested_rid) {
                    _this.isFriend = true;
                }
            }
            _this.isFriend = _this.isFriend || false;
        });
    };
    ProfilePage.prototype.invite = function () {
        var _this = this;
        this.graphService.getFriends()
            .then(function () {
            var alert = _this.alertCtrl.create();
            alert.setTitle('Invite');
            alert.setSubTitle('Select a friend to invite.');
            alert.addButton('Confirm');
            alert.addInput({
                name: 'radio1',
                type: 'radio',
                label: 'Radio 1',
                value: 'value1',
                checked: true
            });
            _this.graphService.graph.friends.map(function (friend) {
                return friend;
            });
            alert.present();
        });
    };
    ProfilePage.prototype.addFriend = function () {
        var _this = this;
        var info;
        var buttons = [];
        buttons.push({
            text: 'Add',
            handler: function (data) {
                // camera permission was granted
                var requester_rid = _this.graphService.graph.rid;
                var requested_rid = _this.item.rid;
                if (requester_rid && requested_rid) {
                    // get rid from bulletin secrets
                }
                else {
                    requester_rid = '';
                    requested_rid = '';
                }
                //////////////////////////////////////////////////////////////////////////
                // create and send transaction to create the relationship on the blockchain
                //////////////////////////////////////////////////////////////////////////
                var not_this_address = foobar.bitcoin.ECPair.fromPublicKeyBuffer(foobar.Buffer.Buffer.from(_this.item.public_key, 'hex')).getAddress();
                for (var h = 0; h < _this.item.outputs.length; h++) {
                    if (_this.item.outputs[h].to != not_this_address) {
                        var address = _this.item.outputs[h].to;
                    }
                }
                _this.walletService.get().then(function () {
                    var raw_dh_private_key = window.crypto.getRandomValues(new Uint8Array(32));
                    var raw_dh_public_key = X25519.getPublic(raw_dh_private_key);
                    var dh_private_key = _this.toHex(raw_dh_private_key);
                    var dh_public_key = _this.toHex(raw_dh_public_key);
                    return _this.transactionService.generateTransaction({
                        relationship: {
                            dh_private_key: dh_private_key,
                            their_bulletin_secret: _this.item.relationship.their_bulletin_secret,
                            their_username: _this.item.relationship.their_username,
                            my_bulletin_secret: _this.bulletinSecretService.generate_bulletin_secret(),
                            my_username: _this.bulletinSecretService.username
                        },
                        dh_public_key: dh_public_key,
                        requested_rid: requested_rid,
                        requester_rid: requester_rid,
                        to: _this.item.relationship.group === true ? _this.item.relationship.their_address : address
                    });
                }).then(function (hash) {
                    return _this.transactionService.sendTransaction();
                }).then(function (txn) {
                    var alert = _this.alertCtrl.create();
                    alert.setTitle('Friend Request Sent');
                    alert.setSubTitle('Your Friend Request has been sent successfully.');
                    alert.addButton('Ok');
                    alert.present();
                }).catch(function (err) {
                    console.log(err);
                });
            }
        });
        var alert = this.alertCtrl.create({
            buttons: buttons
        });
        alert.setTitle('Add friend');
        alert.setSubTitle('Do you want to add ' + this.item.relationship.their_username + '?');
        alert.present();
    };
    ProfilePage.prototype.joinGroup = function () {
        var _this = this;
        return this.ahttp.get(this.settingsService.remoteSettings['baseUrl'] + '/ns?requested_rid=' + this.item.rid + '&bulletin_secret=' + this.bulletinSecretService.bulletin_secret)
            .subscribe(function (res) {
            return new Promise(function (resolve, reject) {
                var invite = res.json();
                var raw_dh_private_key = window.crypto.getRandomValues(new Uint8Array(32));
                var raw_dh_public_key = X25519.getPublic(raw_dh_private_key);
                var dh_private_key = _this.toHex(raw_dh_private_key);
                var dh_public_key = _this.toHex(raw_dh_public_key);
                resolve({
                    their_address: invite.their_address,
                    their_public_key: invite.their_public_key,
                    their_bulletin_secret: invite.their_bulletin_secret,
                    their_username: invite.their_username,
                    dh_public_key: dh_public_key,
                    dh_private_key: dh_private_key,
                    requested_rid: invite.requested_rid,
                    requester_rid: _this.graphService.graph.rid
                });
            })
                .then(function (info) {
                return _this.transactionService.generateTransaction({
                    relationship: {
                        dh_private_key: info.dh_private_key,
                        my_bulletin_secret: _this.bulletinSecretService.generate_bulletin_secret(),
                        my_username: _this.bulletinSecretService.username,
                        their_address: info.their_address,
                        their_public_key: info.their_public_key,
                        their_bulletin_secret: info.their_bulletin_secret,
                        their_username: info.their_username,
                        group: true
                    },
                    requester_rid: info.requester_rid,
                    requested_rid: info.requested_rid,
                    dh_public_key: info.dh_public_key,
                    to: info.their_address
                });
            }).then(function (txn) {
                return _this.transactionService.sendTransaction();
            })
                .then(function (hash) {
                if (_this.settingsService.remoteSettings['walletUrl']) {
                    return _this.graphService.getInfo();
                }
            })
                .then(function () {
                return _this.refresh(null);
            })
                .then(function () {
                _this.events.publish('pages-settings');
            })
                .catch(function (err) {
                _this.events.publish('pages');
            });
        });
    };
    ProfilePage.prototype.message = function () {
        var page = this.item.relationship.group === true ? __WEBPACK_IMPORTED_MODULE_9__group_group__["a" /* GroupPage */] : __WEBPACK_IMPORTED_MODULE_8__chat_chat__["a" /* ChatPage */];
        this.navCtrl.push(page, {
            item: {
                transaction: this.item
            }
        });
    };
    ProfilePage.prototype.showFriendRequests = function () {
        var item = { pageTitle: { title: "Friend Requests" } };
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_7__list_list__["a" /* ListPage */], item);
    };
    ProfilePage.prototype.toHex = function (byteArray) {
        var callback = function (byte) {
            return ('0' + (byte & 0xFF).toString(16)).slice(-2);
        };
        return Array.from(byteArray, callback).join('');
    };
    ProfilePage = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["n" /* Component */])({
            selector: 'page-profile',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/profile/profile.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n  </ion-navbar>\n</ion-header>\n<ion-content padding>\n  <ion-row>\n    <ion-col text-center>\n      <ion-item>\n        <h1>{{item.relationship.their_username}}</h1></ion-item>\n    </ion-col>\n    <ion-col>\n      <button ion-button large secondary (click)="addFriend()" *ngIf="isFriend === false && item.relationship.group !== true">\n        Add friend&nbsp;<ion-icon name="create"></ion-icon>\n      </button>\n      <button ion-button large secondary (click)="joinGroup()" *ngIf="isFriend === false && item.relationship.group === true">\n        Join group&nbsp;<ion-icon name="create"></ion-icon>\n      </button>\n      <button ion-button large secondary (click)="message()" *ngIf="isFriend === true">\n        {{item.relationship.group === true ? "Group" : "Direct"}} message&nbsp;<ion-icon name="create"></ion-icon>\n      </button>\n      <button ion-button large secondary (click)="invite()" *ngIf="isFriend === true">\n        Invite&nbsp;<ion-icon name="create"></ion-icon>\n      </button>\n      <button ion-button large secondary (click)="refer()" *ngIf="isFriend === true">\n        Refer&nbsp;<ion-icon name="create"></ion-icon>\n      </button>\n    </ion-col>\n  </ion-row>\n</ion-content>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/profile/profile.html"*/
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["i" /* NavController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["j" /* NavParams */],
            __WEBPACK_IMPORTED_MODULE_2__ionic_storage__["b" /* Storage */],
            __WEBPACK_IMPORTED_MODULE_5__app_wallet_service__["a" /* WalletService */],
            __WEBPACK_IMPORTED_MODULE_3__app_graph_service__["a" /* GraphService */],
            __WEBPACK_IMPORTED_MODULE_4__app_bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_10__angular_http__["b" /* Http */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["f" /* LoadingController */],
            __WEBPACK_IMPORTED_MODULE_11__app_settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["a" /* AlertController */],
            __WEBPACK_IMPORTED_MODULE_6__app_transaction_service__["a" /* TransactionService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["l" /* ToastController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["b" /* Events */]])
    ], ProfilePage);
    return ProfilePage;
}());

//# sourceMappingURL=profile.js.map

/***/ })

},[326]);
//# sourceMappingURL=main.js.map