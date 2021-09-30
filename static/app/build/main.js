webpackJsonp([0],{

/***/ 134:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return ComposePage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(9);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__app_autocomplete_provider__ = __webpack_require__(223);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__angular_forms__ = __webpack_require__(34);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4_ionic2_auto_complete__ = __webpack_require__(380);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_graph_service__ = __webpack_require__(26);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_transaction_service__ = __webpack_require__(29);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__app_wallet_service__ = __webpack_require__(24);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__app_bulletinSecret_service__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__angular_http__ = __webpack_require__(21);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_10__app_settings_service__ = __webpack_require__(22);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};











var ComposePage = /** @class */ (function () {
    function ComposePage(navCtrl, navParams, completeTestService, graphService, transactionService, walletService, alertCtrl, bulletinSecretService, ahttp, settingsService) {
        this.navCtrl = navCtrl;
        this.completeTestService = completeTestService;
        this.graphService = graphService;
        this.transactionService = transactionService;
        this.walletService = walletService;
        this.alertCtrl = alertCtrl;
        this.bulletinSecretService = bulletinSecretService;
        this.ahttp = ahttp;
        this.settingsService = settingsService;
        this.myForm = new __WEBPACK_IMPORTED_MODULE_3__angular_forms__["b" /* FormGroup */]({
            searchTerm: new __WEBPACK_IMPORTED_MODULE_3__angular_forms__["a" /* FormControl */]('', [__WEBPACK_IMPORTED_MODULE_3__angular_forms__["g" /* Validators */].required])
        });
        this.item = navParams.data.item;
        this.mode = navParams.data.mode || 'new';
        this.thread = navParams.data.thread;
        this.recipient = '';
        this.prevBody = '';
    }
    ComposePage.prototype.ionViewDidEnter = function () {
        if (this.mode === 'reply') {
            this.recipient = this.item.sender;
            this.subject = this.item.subject;
            this.prevBody = this.item.body;
            this.message_type = 'mail';
        }
        else if (this.mode === 'replyToAll') {
            this.recipient = this.item.group;
            this.subject = this.item.subject;
            this.prevBody = this.item.body;
            this.message_type = 'group_mail';
        }
        else if (this.mode === 'forward') {
            this.subject = this.item.subject;
            this.body = this.item.body;
        }
        else if (this.mode === 'sign') {
            this.recipient = this.item.sender;
            this.subject = this.item.subject;
            this.body = this.item.body;
            this.message_type = 'contract_signed';
            this.submit();
        }
        else if (this.item && this.item.recipient) {
            this.recipient = this.item.recipient;
            this.message_type = this.graphService.isGroup(this.recipient) ? 'group_mail' : 'mail';
        }
        else {
            this.message_type = 'mail';
        }
    };
    ComposePage.prototype.changeListener = function ($event) {
        var _this = this;
        this.busy = true;
        this.filepath = $event.target.files[0].name;
        var reader = new FileReader();
        reader.readAsDataURL($event.target.files[0]);
        reader.onload = function () {
            _this.filedata = reader.result.toString().substr(22);
            _this.ahttp.post(_this.settingsService.remoteSettings['baseUrl'] + '/sia-upload?filename=' + encodeURIComponent(_this.filepath), { file: _this.filedata })
                .subscribe(function (res) {
                var data = res.json();
                if (!data.skylink)
                    return;
                _this.skylink = data.skylink;
                _this.busy = false;
            });
        };
        reader.onerror = function () { };
    };
    ComposePage.prototype.submit = function () {
        var _this = this;
        var alert = this.alertCtrl.create();
        alert.setTitle('Send mail confirmation');
        alert.setSubTitle('Are you sure?');
        alert.addButton('Cancel');
        alert.addButton({
            text: 'Confirm',
            handler: function (data) {
                _this.walletService.get()
                    .then(function () {
                    var rid = _this.graphService.generateRid(_this.bulletinSecretService.identity.username_signature, _this.recipient.username_signature);
                    var requester_rid = _this.graphService.generateRid(_this.bulletinSecretService.identity.username_signature, _this.bulletinSecretService.identity.username_signature, _this.message_type);
                    var requested_rid = _this.graphService.generateRid(_this.recipient.username_signature, _this.recipient.username_signature, _this.message_type);
                    if (_this.graphService.isGroup(_this.recipient)) {
                        return _this.transactionService.generateTransaction({
                            relationship: {
                                envelope: {
                                    sender: _this.bulletinSecretService.identity,
                                    subject: _this.subject,
                                    body: _this.body,
                                    thread: _this.thread,
                                    message_type: _this.message_type,
                                    event_datetime: _this.event_datetime,
                                    skylink: _this.skylink,
                                    filename: _this.filepath
                                }
                            },
                            rid: rid,
                            requester_rid: requester_rid,
                            requested_rid: requested_rid,
                            group: true,
                            group_username_signature: _this.recipient.username_signature
                        });
                    }
                    else {
                        var dh_public_key = _this.graphService.keys[rid].dh_public_keys[0];
                        var dh_private_key = _this.graphService.keys[rid].dh_private_keys[0];
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
                                    envelope: {
                                        subject: _this.subject,
                                        body: _this.body,
                                        thread: _this.thread,
                                        message_type: _this.message_type,
                                        event_datetime: _this.event_datetime,
                                        skylink: _this.skylink,
                                        filename: _this.filepath
                                    }
                                },
                                shared_secret: shared_secret,
                                rid: rid,
                                requester_rid: requester_rid,
                                requested_rid: requested_rid
                            });
                        }
                        else {
                            return new Promise(function (resolve, reject) {
                                var alert = _this.alertCtrl.create();
                                alert.setTitle('Contact not yet processed');
                                alert.setSubTitle('Please wait a few minutes and try again');
                                alert.addButton('Ok');
                                alert.present();
                                return reject('failed to create friend request');
                            });
                        }
                    }
                }).then(function (txn) {
                    return _this.transactionService.sendTransaction();
                }).then(function () {
                    _this.navCtrl.pop();
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
    ComposePage.prototype.toHex = function (byteArray) {
        var callback = function (byte) {
            return ('0' + (byte & 0xFF).toString(16)).slice(-2);
        };
        return Array.from(byteArray, callback).join('');
    };
    __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["_14" /* ViewChild */])('searchbar'),
        __metadata("design:type", __WEBPACK_IMPORTED_MODULE_4_ionic2_auto_complete__["a" /* AutoCompleteComponent */])
    ], ComposePage.prototype, "searchbar", void 0);
    ComposePage = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["n" /* Component */])({
            selector: 'compose-profile',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/mail/compose.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n  </ion-navbar>\n</ion-header>\n<ion-content padding>\n  What type of message is this?\n  <ion-segment [(ngModel)]="message_type">\n    <ion-segment-button value="mail" *ngIf="!graphService.isGroup(recipient)">\n      Mail\n    </ion-segment-button>\n    <ion-segment-button value="group_mail" *ngIf="graphService.isGroup(recipient)">\n      Mail\n    </ion-segment-button>\n    <ion-segment-button value="contract">\n      Contract\n    </ion-segment-button>\n    <ion-segment-button value="event_meeting">\n      Event / Meeting\n    </ion-segment-button>\n  </ion-segment>\n  <button ion-button secondary (click)="submit()" [disabled]="busy">Send \n    <ion-spinner *ngIf="busy"></ion-spinner>\n  </button>\n  <form [formGroup]="myForm" (ngSubmit)="submit()" *ngIf="!recipient">\n    <ion-auto-complete #searchbar [(ngModel)]="recipient" [options]="{ placeholder : \'Recipient\' }" [dataProvider]="completeTestService" formControlName="searchTerm" required></ion-auto-complete>\n  </form>\n  <ion-item *ngIf="message_type === \'event_meeting\'">\n    <ion-label floating>Date &amp; time</ion-label>\n    <ion-datetime displayFormat="D MMM YYYY H:mm" [(ngModel)]="event_datetime"></ion-datetime>\n  </ion-item>\n  <ion-item *ngIf="recipient" title="Verified" class="sender">{{recipient.username}} <ion-icon name="checkmark-circle" class="success"></ion-icon></ion-item>\n  <ion-item>\n    <ion-label floating>Subject</ion-label>\n    <ion-input type="text" [(ngModel)]="subject"></ion-input>\n  </ion-item>\n  <ion-item>\n    <ion-label floating>Body</ion-label>\n    <ion-textarea type="text" [(ngModel)]="body" rows="5" autoGrow="true"></ion-textarea>\n  </ion-item>\n  <ion-item *ngIf="settingsService.remoteSettings.restricted">\n    <ion-label id="profile_image" color="primary"></ion-label>\n    <ion-input type="file" (change)="changeListener($event)"></ion-input>\n  </ion-item>\n  <br>\n  <ion-item *ngIf="item && item.sender">\n    Previous message\n    <div title="Verified" class="sender">\n      <span>{{item.sender.username}} <ion-icon name="checkmark-circle" class="success"></ion-icon></span>\n      <span *ngIf="item.group">{{item.group.username}} <ion-icon name="checkmark-circle" class="success"></ion-icon></span>\n    </div>\n    <div class="subject">{{item.subject}}</div>\n    <div class="datetime">{{item.datetime}}</div>\n    <div class="body">{{item.body}}</div>\n  </ion-item>\n</ion-content>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/mail/compose.html"*/
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["i" /* NavController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["j" /* NavParams */],
            __WEBPACK_IMPORTED_MODULE_2__app_autocomplete_provider__["a" /* CompleteTestService */],
            __WEBPACK_IMPORTED_MODULE_5__app_graph_service__["a" /* GraphService */],
            __WEBPACK_IMPORTED_MODULE_6__app_transaction_service__["a" /* TransactionService */],
            __WEBPACK_IMPORTED_MODULE_7__app_wallet_service__["a" /* WalletService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["a" /* AlertController */],
            __WEBPACK_IMPORTED_MODULE_8__app_bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_9__angular_http__["b" /* Http */],
            __WEBPACK_IMPORTED_MODULE_10__app_settings_service__["a" /* SettingsService */]])
    ], ComposePage);
    return ComposePage;
}());

//# sourceMappingURL=compose.js.map

/***/ }),

/***/ 135:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return OpenGraphParserService; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__angular_http__ = __webpack_require__(21);
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

/***/ 18:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return BulletinSecretService; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__ionic_storage__ = __webpack_require__(42);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2_ionic_angular__ = __webpack_require__(9);
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
        this.username_signature = null;
        this.keyname = null;
        this.keykeys = null;
        this.username = null;
        this.public_key = null;
        this.identity = {
            username: '',
            username_signature: '',
            public_key: '',
        };
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
                _this.public_key = _this.key.getPublicKeyBuffer().toString('hex');
                _this.identity = {
                    username: _this.username,
                    username_signature: _this.username_signature,
                    public_key: _this.public_key
                };
                _this.username_signature = _this.generate_username_signature();
                return resolve();
            });
        });
    };
    BulletinSecretService.prototype.identityJson = function () {
        return JSON.stringify(this.identity, null, 4);
    };
    BulletinSecretService.prototype.generate_username_signature = function () {
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
                .catch(function (err) {
                return reject(err);
            });
        });
    };
    BulletinSecretService.prototype.create = function (username) {
        var _this = this;
        return new Promise(function (resolve, reject) {
            if (!username)
                return reject('username missing');
            _this.keyname = 'usernames-' + username;
            _this.storage.set('last-keyname', _this.keyname);
            _this.username = username;
            _this.key = foobar.bitcoin.ECPair.makeRandom();
            _this.storage.set(_this.keyname, _this.key.toWIF());
            _this.username_signature = _this.generate_username_signature();
            return _this.get().then(function () {
                return resolve();
            });
        });
    };
    BulletinSecretService.prototype.import = function (keyWif, username) {
        var _this = this;
        return new Promise(function (resolve, reject) {
            if (!username)
                return reject('username missing');
            _this.keyname = 'usernames-' + username;
            _this.storage.set('last-keyname', _this.keyname);
            _this.username = username;
            _this.storage.set(_this.keyname, keyWif.trim());
            _this.key = foobar.bitcoin.ECPair.fromWIF(keyWif.trim());
            _this.username_signature = _this.generate_username_signature();
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
    BulletinSecretService.prototype.unset = function () {
        this.key = null;
        this.username_signature = null;
        this.keyname = null;
        this.keykeys = null;
        this.username = null;
        this.public_key = null;
        this.identity = {
            username: '',
            username_signature: '',
            public_key: '',
        };
    };
    BulletinSecretService.prototype.publicKeyToAddress = function (public_key) {
        foobar.bitcoin.ECPair.fromPublicKeyBuffer(foobar.Buffer.Buffer.from(public_key, 'hex')).getAddress();
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

/***/ 22:
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
        this.tokens = {};
        this.menu = '';
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

/***/ 220:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return HomePage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__angular_forms__ = __webpack_require__(34);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2_ionic_angular__ = __webpack_require__(9);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__ionic_storage__ = __webpack_require__(42);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_bulletinSecret_service__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_wallet_service__ = __webpack_require__(24);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_graph_service__ = __webpack_require__(26);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__app_transaction_service__ = __webpack_require__(29);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__app_peer_service__ = __webpack_require__(221);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__list_list__ = __webpack_require__(61);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_10__profile_profile__ = __webpack_require__(62);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_11__app_opengraphparser_service__ = __webpack_require__(135);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_12__ionic_native_social_sharing__ = __webpack_require__(106);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_13__app_settings_service__ = __webpack_require__(22);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_14__app_firebase_service__ = __webpack_require__(224);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_15__angular_http__ = __webpack_require__(21);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_16__app_autocomplete_provider__ = __webpack_require__(223);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : new P(function (resolve) { resolve(result.value); }).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
var __generator = (this && this.__generator) || function (thisArg, body) {
    var _ = { label: 0, sent: function() { if (t[0] & 1) throw t[1]; return t[1]; }, trys: [], ops: [] }, f, y, t, g;
    return g = { next: verb(0), "throw": verb(1), "return": verb(2) }, typeof Symbol === "function" && (g[Symbol.iterator] = function() { return this; }), g;
    function verb(n) { return function (v) { return step([n, v]); }; }
    function step(op) {
        if (f) throw new TypeError("Generator is already executing.");
        while (_) try {
            if (f = 1, y && (t = op[0] & 2 ? y["return"] : op[0] ? y["throw"] || ((t = y["return"]) && t.call(y), 0) : y.next) && !(t = t.call(y, op[1])).done) return t;
            if (y = 0, t) op = [op[0] & 2, t.value];
            switch (op[0]) {
                case 0: case 1: t = op; break;
                case 4: _.label++; return { value: op[1], done: false };
                case 5: _.label++; y = op[1]; op = [0]; continue;
                case 7: op = _.ops.pop(); _.trys.pop(); continue;
                default:
                    if (!(t = _.trys, t = t.length > 0 && t[t.length - 1]) && (op[0] === 6 || op[0] === 2)) { _ = 0; continue; }
                    if (op[0] === 3 && (!t || (op[1] > t[0] && op[1] < t[3]))) { _.label = op[1]; break; }
                    if (op[0] === 6 && _.label < t[1]) { _.label = t[1]; t = op; break; }
                    if (t && _.label < t[2]) { _.label = t[2]; _.ops.push(op); break; }
                    if (t[2]) _.ops.pop();
                    _.trys.pop(); continue;
            }
            op = body.call(thisArg, _);
        } catch (e) { op = [6, e]; y = 0; } finally { f = t = 0; }
        if (op[0] & 5) throw op[1]; return { value: op[0] ? op[1] : void 0, done: true };
    }
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
        this.origin = encodeURIComponent(this.location.origin);
        this.prefix = 'usernames-';
        this.refresh(null);
        if (this.settingsService.remoteSettings.restricted) {
            this.busy = true;
            this.graphService.identityToSkylink(this.bulletinSecretService.identity)
                .then(function (skylink) {
                _this.identitySkylink = skylink;
                _this.busy = false;
            });
        }
    }
    HomePage.prototype.submit = function () {
        if (!this.myForm.valid)
            return false;
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_10__profile_profile__["a" /* ProfilePage */], { item: this.myForm.value.searchTerm });
        console.log(this.myForm.value.searchTerm);
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
                    'username_signature': _this.bulletinSecretService.username_signature
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
    HomePage.prototype.addOrganization = function () {
        var _this = this;
        console.log('submitted');
        this.inviteBusy = true;
        var username_signature = foobar.base64.fromByteArray(this.bulletinSecretService.key.sign(foobar.bitcoin.crypto.sha256(this.organizationIdentifier)).toDER());
        var invite = {
            identifier: this.organizationIdentifier,
            invite_signature: username_signature,
            parent: this.graphService.toIdentity(this.bulletinSecretService.identity)
        };
        this.graphService.inviteToSkylink(invite)
            .then(function (skylink) {
            invite.skylink = skylink;
            return fetch('/invite-organization', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(invite),
            });
        })
            .then(function (res) { return __awaiter(_this, void 0, void 0, function () {
            var _a, _b;
            return __generator(this, function (_c) {
                switch (_c.label) {
                    case 0:
                        _b = (_a = console).log;
                        return [4 /*yield*/, res.json()];
                    case 1:
                        _b.apply(_a, [_c.sent()]);
                        this.getOrganizations();
                        this.organizationIdentifier = null;
                        this.inviteBusy = false;
                        return [2 /*return*/];
                }
            });
        }); });
        return false;
    };
    HomePage.prototype.getOrganizations = function () {
        var _this = this;
        return fetch('/invite-organization?username_signature=' + encodeURIComponent(this.bulletinSecretService.identity.username_signature))
            .then(function (res) { return __awaiter(_this, void 0, void 0, function () {
            var result, users, i, user;
            return __generator(this, function (_a) {
                switch (_a.label) {
                    case 0: return [4 /*yield*/, res.json()];
                    case 1:
                        result = _a.sent();
                        this.invites = [];
                        users = result.users;
                        users.sort(function (a, b) {
                            try {
                                var ausername = a.user.username;
                                var busername = b.user.username;
                                if (ausername.toLowerCase() < busername.toLowerCase())
                                    return -1;
                                if (ausername.toLowerCase() > busername.toLowerCase())
                                    return 1;
                                return 0;
                            }
                            catch (err) {
                                return 0;
                            }
                        });
                        for (i = 0; i < users.length; i++) {
                            user = users[i];
                            this.invites.push(user);
                        }
                        return [2 /*return*/];
                }
            });
        }); });
    };
    HomePage.prototype.addOrganizationMember = function () {
        var _this = this;
        console.log('submitted');
        this.inviteBusy = true;
        var username_signature = foobar.base64.fromByteArray(this.bulletinSecretService.key.sign(foobar.bitcoin.crypto.sha256(this.memberIdentifier)).toDER());
        var invite = {
            identifier: this.memberIdentifier,
            invite_signature: username_signature,
            parent: this.graphService.toIdentity(this.bulletinSecretService.identity)
        };
        this.graphService.inviteToSkylink(invite)
            .then(function (skylink) {
            invite.skylink = skylink;
            return fetch('/invite-organization-user', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(invite),
            });
        })
            .then(function (res) { return __awaiter(_this, void 0, void 0, function () {
            var _a, _b;
            return __generator(this, function (_c) {
                switch (_c.label) {
                    case 0:
                        _b = (_a = console).log;
                        return [4 /*yield*/, res.json()];
                    case 1:
                        _b.apply(_a, [_c.sent()]);
                        this.getOrganizationMembers();
                        this.memberIdentifier = null;
                        this.inviteBusy = false;
                        return [2 /*return*/];
                }
            });
        }); });
        return false;
    };
    HomePage.prototype.getOrganizationMembers = function () {
        var _this = this;
        return fetch('/invite-organization-user?username_signature=' + encodeURIComponent(this.bulletinSecretService.identity.username_signature))
            .then(function (res) { return __awaiter(_this, void 0, void 0, function () {
            var result, users, i, user;
            return __generator(this, function (_a) {
                switch (_a.label) {
                    case 0: return [4 /*yield*/, res.json()];
                    case 1:
                        result = _a.sent();
                        this.invites = [];
                        users = result.users;
                        users.sort(function (a, b) {
                            try {
                                var ausername = a.user.username;
                                var busername = b.user.username;
                                if (ausername.toLowerCase() < busername.toLowerCase())
                                    return -1;
                                if (ausername.toLowerCase() > busername.toLowerCase())
                                    return 1;
                                return 0;
                            }
                            catch (err) {
                                return 0;
                            }
                        });
                        for (i = 0; i < users.length; i++) {
                            user = users[i];
                            this.invites.push(user);
                        }
                        return [2 /*return*/];
                }
            });
        }); });
    };
    HomePage.prototype.addMemberContact = function () {
        var _this = this;
        console.log('submitted');
        this.inviteBusy = true;
        var username_signature = foobar.base64.fromByteArray(this.bulletinSecretService.key.sign(foobar.bitcoin.crypto.sha256(this.contactIdentifier)).toDER());
        var invite = {
            identifier: this.contactIdentifier,
            invite_signature: username_signature,
            parent: this.graphService.toIdentity(this.bulletinSecretService.identity)
        };
        this.graphService.inviteToSkylink(invite)
            .then(function (skylink) {
            invite.skylink = skylink;
            return fetch('/invite-member-contact', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(invite),
            });
        })
            .then(function (res) { return __awaiter(_this, void 0, void 0, function () {
            var _a, _b;
            return __generator(this, function (_c) {
                switch (_c.label) {
                    case 0:
                        _b = (_a = console).log;
                        return [4 /*yield*/, res.json()];
                    case 1:
                        _b.apply(_a, [_c.sent()]);
                        this.getMemberContacts();
                        this.contactIdentifier = null;
                        this.inviteBusy = false;
                        return [2 /*return*/];
                }
            });
        }); });
        return false;
    };
    HomePage.prototype.getMemberContacts = function () {
        var _this = this;
        return fetch('/invite-member-contact?username_signature=' + encodeURIComponent(this.bulletinSecretService.identity.username_signature))
            .then(function (res) { return __awaiter(_this, void 0, void 0, function () {
            var result, users, i, user;
            return __generator(this, function (_a) {
                switch (_a.label) {
                    case 0: return [4 /*yield*/, res.json()];
                    case 1:
                        result = _a.sent();
                        this.invites = [];
                        users = result.users;
                        users.sort(function (a, b) {
                            try {
                                var ausername = a.user.username;
                                var busername = b.user.username;
                                if (ausername.toLowerCase() < busername.toLowerCase())
                                    return -1;
                                if (ausername.toLowerCase() > busername.toLowerCase())
                                    return 1;
                                return 0;
                            }
                            catch (err) {
                                return 0;
                            }
                        });
                        for (i = 0; i < users.length; i++) {
                            user = users[i];
                            this.invites.push(user);
                        }
                        return [2 /*return*/];
                }
            });
        }); });
    };
    HomePage.prototype.showChat = function () {
        var item = { pageTitle: { title: "Chat" } };
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_9__list_list__["a" /* ListPage */], item);
    };
    HomePage.prototype.showFriendRequests = function () {
        var item = { pageTitle: { title: "Friend Requests" } };
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_9__list_list__["a" /* ListPage */], item);
    };
    HomePage.prototype.refresh = function (refresher) {
        this.loading = false;
        if (this.bulletinSecretService.identity.type === 'admin') {
            this.getOrganizations();
        }
        else if (this.bulletinSecretService.identity.type === 'organization') {
            this.getOrganizationMembers();
        }
        else if (this.bulletinSecretService.identity.type === 'organization_member') {
            this.getMemberContacts();
        }
    };
    HomePage.prototype.search = function () {
        var _this = this;
        return this.ahttp.get(this.settingsService.remoteSettings['baseUrl'] + '/search?searchTerm=' + this.searchTerm)
            .subscribe(function (res) {
            _this.searchResults = res.json();
        }, function () { });
    };
    HomePage.prototype.createGeoWallet = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            _this.loadingModal = _this.loadingCtrl.create({
                content: 'Burying treasure at this location...'
            });
            return _this.loadingModal.present()
                .then(function () {
                return resolve();
            });
        })
            .then(function () {
            return _this.graphService.createRecovery(_this.bulletinSecretService.username);
        })
            .then(function () {
            return _this.loadingModal.dismiss();
        });
    };
    HomePage.prototype.createGroup = function () {
        var _this = this;
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
        })
            .then(function (groupName) {
            return _this.graphService.createGroup(groupName);
        })
            .then(function () {
            return _this.refresh(null);
        })
            .catch(function (err) {
            console.log(err);
            _this.events.publish('pages');
        });
    };
    HomePage.prototype.signInToDashboard = function () {
        var _this = this;
        fetch('/generate-session-uuid')
            .then(function (res) {
            return res.json();
        })
            .then(function (data) {
            var session_id_signature = foobar.base64.fromByteArray(_this.bulletinSecretService.key.sign(foobar.bitcoin.crypto.sha256(data.session_uuid)).toDER());
            return fetch('/organization-sign-in', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    user: {
                        username_signature: _this.bulletinSecretService.identity.username_signature
                    },
                    session_id_signature: session_id_signature
                }),
            });
        })
            .then(function (res) {
            open('/dashboard', '_blank');
        });
    };
    HomePage.prototype.itemTapped = function (event, item) {
        item.pageTitle = "Posts";
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_9__list_list__["a" /* ListPage */], {
            item: item
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
            selector: 'page-home',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/home/home.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n  </ion-navbar>\n</ion-header>\n\n<ion-content padding>\n  <ion-spinner *ngIf="loading"></ion-spinner>\n  <ion-row>\n    <ion-col col-lg-12 col-md-12 col-sm-12 *ngIf="!settingsService.remoteSettings.restricted || (settingsService.remoteSettings.restricted && settingsService.remoteSettings.identity.username_signature === bulletinSecretService.identity.username_signature)">\n      <button ion-button large secondary (click)="createGroup()">\n        Create Group&nbsp;<ion-icon name="create"></ion-icon>\n      </button>\n    </ion-col>\n    <ion-col col-lg-12 col-md-12 col-sm-12 *ngIf="graphService.registrationStatus() === \'error\'">\n      Something went wrong with your registration, contact info@centeridentity.com for assistance.\n    </ion-col>\n    <ion-col col-lg-12 col-md-12 col-sm-12 *ngIf="graphService.registrationStatus() === \'pending\'">\n      Registration is pending approval.\n    </ion-col>\n    <ion-col col-lg-12 col-md-12 col-sm-12 *ngIf="graphService.registrationStatus() === \'complete\' && settingsService.remoteSettings.restricted">\n      <h1>Welcome!</h1>\n    </ion-col>\n    <ion-col col-lg-12 col-md-12 col-sm-12 *ngIf="!settingsService.remoteSettings.restricted">\n      <h1>Welcome!</h1>\n      <h4>Public identity (share this with everyone) <ion-spinner *ngIf="busy"></ion-spinner></h4>\n      <ion-item *ngIf="settingsService.remoteSettings.restricted">\n        <ion-textarea type="text" [(ngModel)]="identitySkylink" autoGrow="true" rows=1></ion-textarea>\n      </ion-item>\n      <ion-item *ngIf="!settingsService.remoteSettings.restricted">\n        <ion-textarea type="text" [value]="bulletinSecretService.identityJson()" autoGrow="true" rows=5></ion-textarea>\n      </ion-item>\n    </ion-col>\n  </ion-row>\n  <ion-row *ngIf="settingsService.remoteSettings.restricted && bulletinSecretService.identity.type === \'admin\'">\n    <ion-col col-lg-6 col-md-6 col-sm-12>\n      <h3>Invite organizations</h3>\n      <ion-item>\n        <ion-label floating>Identifier <ion-spinner *ngIf="inviteBusy"></ion-spinner></ion-label>\n        <ion-input type="text" [(ngModel)]="organizationIdentifier"></ion-input>\n      </ion-item>\n      <ion-item>\n        <button ion-button large secondary (click)="addOrganization()" [disabled]="!organizationIdentifier || inviteBusy">\n          Add organization&nbsp;<ion-icon name="create"></ion-icon>\n        </button>\n      </ion-item>\n    </ion-col>\n    <ion-col col-lg-6 col-md-6 col-sm-12 *ngIf="invites">\n      <h3>Invites</h3>\n      <ion-list *ngFor="let invite of invites">\n        <ion-item ion-item>\n          <ion-icon name="person" item-start [color]="\'dark\'"></ion-icon>\n          {{invite.username}}\n        </ion-item>\n        <ion-item>\n          <ion-label floating>Invite code</ion-label>\n          <ion-input type="text" [value]="invite.skylink"></ion-input>\n        </ion-item>\n      </ion-list>\n    </ion-col>\n  </ion-row>\n  <ion-row *ngIf="settingsService.remoteSettings.restricted && bulletinSecretService.identity.type === \'organization\'">\n    <ion-col col-lg-6 col-md-6 col-sm-12>\n      <h3>Invite members</h3>\n      <ion-item>\n        <ion-label floating>Identifier <ion-spinner *ngIf="inviteBusy"></ion-spinner></ion-label>\n        <ion-input type="text" [(ngModel)]="memberIdentifier"></ion-input>\n      </ion-item>\n      <ion-item>\n        <button ion-button large secondary (click)="addOrganizationMember()" [disabled]="!memberIdentifier || inviteBusy">\n          Add organization member&nbsp;<ion-icon name="create"></ion-icon>\n        </button>\n      </ion-item>\n    </ion-col>\n    <ion-col col-lg-6 col-md-6 col-sm-12 *ngIf="invites">\n      <h3>Invites</h3>\n      <ion-list *ngFor="let invite of invites">\n        <ion-item ion-item>\n          <ion-icon name="person" item-start [color]="\'dark\'"></ion-icon>\n          {{invite.user.username}}\n        </ion-item>\n        <ion-item>\n          <ion-label floating>Invite code</ion-label>\n          <ion-input type="text" [value]="invite.skylink"></ion-input>\n        </ion-item>\n      </ion-list>\n    </ion-col>\n  </ion-row>\n  <ion-row *ngIf="settingsService.remoteSettings.restricted && bulletinSecretService.identity.type === \'organization\'">\n    <ion-col col-lg-6 col-md-6 col-sm-12>\n      <h3>Admin</h3>\n      <ion-item>\n        <button ion-button large secondary (click)="signInToDashboard()">\n          Sign-in to Dashboard&nbsp;<ion-icon name="create"></ion-icon>\n        </button>\n      </ion-item>\n    </ion-col>\n  </ion-row>\n  <ion-row *ngIf="settingsService.remoteSettings.restricted && bulletinSecretService.identity.type === \'organization_member\'">\n    <ion-col col-lg-6 col-md-6 col-sm-12>\n      <h3>Invite contacts</h3>\n      <ion-item>\n        <ion-label floating>Identifier <ion-spinner *ngIf="inviteBusy"></ion-spinner></ion-label>\n        <ion-input type="text" [(ngModel)]="contactIdentifier"></ion-input>\n      </ion-item>\n      <ion-item>\n        <button ion-button large secondary (click)="addMemberContact()" [disabled]="!contactIdentifier || inviteBusy">\n          Add contact&nbsp;<ion-icon name="create"></ion-icon>\n        </button>\n      </ion-item>\n    </ion-col>\n    <ion-col col-lg-6 col-md-6 col-sm-12 *ngIf="invites">\n      <h3>Invites</h3>\n      <ion-list *ngFor="let invite of invites">\n        <ion-item ion-item>\n          <ion-icon name="person" item-start [color]="\'dark\'"></ion-icon>\n          {{invite.user.username}}\n        </ion-item>\n        <ion-item>\n          <ion-label floating>Invite code</ion-label>\n          <ion-input type="text" [value]="invite.skylink"></ion-input>\n        </ion-item>\n      </ion-list>\n    </ion-col>\n  </ion-row>\n</ion-content>\n'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/home/home.html"*/
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
            __WEBPACK_IMPORTED_MODULE_11__app_opengraphparser_service__["a" /* OpenGraphParserService */],
            __WEBPACK_IMPORTED_MODULE_12__ionic_native_social_sharing__["a" /* SocialSharing */],
            __WEBPACK_IMPORTED_MODULE_13__app_settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_2_ionic_angular__["f" /* LoadingController */],
            __WEBPACK_IMPORTED_MODULE_15__angular_http__["b" /* Http */],
            __WEBPACK_IMPORTED_MODULE_14__app_firebase_service__["a" /* FirebaseService */],
            __WEBPACK_IMPORTED_MODULE_2_ionic_angular__["b" /* Events */],
            __WEBPACK_IMPORTED_MODULE_2_ionic_angular__["l" /* ToastController */],
            __WEBPACK_IMPORTED_MODULE_8__app_peer_service__["a" /* PeerService */],
            __WEBPACK_IMPORTED_MODULE_16__app_autocomplete_provider__["a" /* CompleteTestService */]])
    ], HomePage);
    return HomePage;
}());

//# sourceMappingURL=home.js.map

/***/ }),

/***/ 221:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return PeerService; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__ionic_storage__ = __webpack_require__(42);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__angular_http__ = __webpack_require__(21);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3_rxjs_operators__ = __webpack_require__(51);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__bulletinSecret_service__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__wallet_service__ = __webpack_require__(24);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__transaction_service__ = __webpack_require__(29);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__settings_service__ = __webpack_require__(22);
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
        this.loading = false;
        this.mode = true;
        this.failedSeedPeers = new Set();
        this.failedConfigPeers = new Set();
    }
    PeerService.prototype.go = function () {
        var _this = this;
        if (this.peerLocked)
            return new Promise(function (resolve, reject) { return resolve(null); });
        return new Promise(function (resolve, reject) {
            var domain = window.location.origin;
            _this.settingsService.remoteSettingsUrl = domain;
            _this.settingsService.remoteSettings = {
                "baseUrl": domain,
                "transactionUrl": domain + "/transaction",
                "fastgraphUrl": domain + "/post-fastgraph-transaction",
                "graphUrl": domain,
                "walletUrl": domain + "/get-graph-wallet",
                "loginUrl": domain + "/login",
                "registerUrl": domain + "/create-relationship",
                "authenticatedUrl": domain + "/authenticated",
                "logoData": "",
                "identity": {}
            };
            return resolve();
        })
            .then(function () {
            return _this.getConfig();
        })
            .then(function () {
            _this.peerLocked = true;
            return _this.storage.set('node', _this.settingsService.remoteSettingsUrl);
        });
    };
    PeerService.prototype.getConfig = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            _this.ahttp.get(_this.settingsService.remoteSettingsUrl + '/yada-config').pipe(Object(__WEBPACK_IMPORTED_MODULE_3_rxjs_operators__["timeout"])(1000)).subscribe(function (res) {
                _this.loading = false;
                var remoteSettings = res.json();
                _this.settingsService.remoteSettings = remoteSettings;
                resolve();
            }, function (err) {
                _this.failedConfigPeers.add(_this.settingsService.remoteSettingsUrl);
                _this.loading = false;
                return reject('config');
            });
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

/***/ 222:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return ChatPage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(9);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__ionic_storage__ = __webpack_require__(42);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_graph_service__ = __webpack_require__(26);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_bulletinSecret_service__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_wallet_service__ = __webpack_require__(24);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_transaction_service__ = __webpack_require__(29);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__app_settings_service__ = __webpack_require__(22);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__list_list__ = __webpack_require__(61);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__profile_profile__ = __webpack_require__(62);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_10__angular_http__ = __webpack_require__(21);
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
        this.identity = this.navParams.get('identity');
        this.label = this.identity.username;
        var rids = this.graphService.generateRids(this.identity);
        this.rid = rids.rid;
        this.requested_rid = rids.requested_rid;
        this.requester_rid = rids.requester_rid;
        this.storage.get('blockchainAddress').then(function (blockchainAddress) {
            _this.blockchainAddress = blockchainAddress;
        });
        this.refresh(null, true);
    }
    ChatPage.prototype.parseChats = function () {
        var group = this.graphService.isGroup(this.identity);
        var rid = group ? this.requested_rid : this.rid;
        if (this.graphService.graph.messages[rid]) {
            this.chats = this.graphService.graph.messages[rid];
            for (var i = 0; i < this.chats.length; i++) {
                if (!group) {
                    this.chats[i].relationship.identity = this.chats[i].public_key === this.bulletinSecretService.identity.public_key ? this.bulletinSecretService.identity : this.graphService.friends_indexed[rid].relationship.identity;
                }
                this.chats[i].time = new Date(parseInt(this.chats[i].time) * 1000).toISOString().slice(0, 19).replace('T', ' ');
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
        return this.graphService.getMessages([this.rid, this.requested_rid])
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
    ChatPage.prototype.changeListener = function ($event) {
        var _this = this;
        this.busy = true;
        this.filepath = $event.target.files[0].name;
        var reader = new FileReader();
        reader.readAsDataURL($event.target.files[0]);
        reader.onload = function () {
            _this.filedata = reader.result.toString().substr(22);
            _this.ahttp.post(_this.settingsService.remoteSettings['baseUrl'] + '/sia-upload?filename=' + encodeURIComponent(_this.filepath), { file: _this.filedata })
                .subscribe(function (res) {
                var data = res.json();
                if (!data.skylink)
                    return;
                _this.skylink = data.skylink;
                _this.busy = false;
                $event.target.value = null;
            });
        };
        reader.onerror = function () { };
    };
    ChatPage.prototype.viewProfile = function (item) {
        var rid = this.graphService.generateRid(item.relationship.identity.username_signature, this.bulletinSecretService.identity.username_signature);
        var identity = this.graphService.friends_indexed[rid];
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_9__profile_profile__["a" /* ProfilePage */], {
            identity: identity ? identity.relationship : item.relationship.identity
        });
    };
    ChatPage.prototype.send = function () {
        var _this = this;
        var alert = this.alertCtrl.create();
        alert.setTitle('Send message');
        alert.setSubTitle('You are about to send a message.');
        alert.addButton('Cancel');
        alert.addButton({
            text: 'Confirm',
            handler: function (data) {
                _this.walletService.get()
                    .then(function () {
                    if (_this.graphService.isGroup(_this.identity)) {
                        return _this.transactionService.generateTransaction({
                            relationship: {
                                chatText: _this.chatText,
                                identity: _this.bulletinSecretService.identity,
                                skylink: _this.skylink,
                                filename: _this.filepath
                            },
                            rid: _this.rid,
                            requester_rid: _this.requester_rid,
                            requested_rid: _this.requested_rid,
                            group: true,
                            group_username_signature: _this.graphService.groups_indexed[_this.requested_rid].relationship.username_signature
                        });
                    }
                    else {
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
                                    chatText: _this.chatText,
                                    skylink: _this.skylink,
                                    filename: _this.filepath
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
                                return reject('failed to create friend request');
                            });
                        }
                    }
                }).then(function (txn) {
                    return _this.transactionService.sendTransaction();
                }).then(function () {
                    _this.chatText = '';
                    _this.skylink = null;
                    _this.filedata = null;
                    _this.filepath = null;
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
            selector: 'page-chat',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/chat/chat.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n    <ion-title>{{label}}</ion-title>\n  </ion-navbar>\n</ion-header>\n<ion-content #content>\n  <ion-refresher (ionRefresh)="refresh($event)">\n    <ion-refresher-content></ion-refresher-content>\n  </ion-refresher>\n  <ion-spinner *ngIf="loading"></ion-spinner>\n	<ion-list>\n	  <ion-item *ngFor="let item of chats" text-wrap>\n        <strong>\n          <span ion-text style="font-size: 20px;" (click)="viewProfile(item)">{{item.relationship.identity ? item.relationship.identity.username : \'Anonymous\'}}</span>\n        </strong>\n        <span style="font-size: 10px; color: rgb(88, 88, 88);" ion-text>{{item.time}}</span>\n        <h3 *ngIf="!item.relationship.isInvite">{{item.relationship.chatText}}</h3>\n        <h3 *ngIf="item.relationship.isInvite && item.relationship.chatText.group === true">Invite to join {{item.relationship.chatText.username}}</h3>\n        <button *ngIf="item.relationship.isInvite && item.relationship.chatText.group === true" ion-button (click)="joinGroup(item)">Join group</button>\n        <button *ngIf="item.relationship.isInvite && item.relationship.chatText.group !== true" ion-button (click)="requestFriend(item)">Join group</button>\n        <a href="https://centeridentity.com/skynet/skylink/{{item.relationship.skylink}}" target="_blank" *ngIf="item.relationship.skylink">Download {{item.relationship.filename}}</a>\n        <hr />\n	  </ion-item>\n	</ion-list>\n</ion-content>\n<ion-footer>\n  <ion-item>\n    <ion-label floating>Chat text</ion-label>\n    <ion-input [(ngModel)]="chatText" (keyup.enter)="send()"></ion-input>\n  </ion-item>\n  <button ion-button (click)="send()" [disabled]="busy">Send <ion-spinner *ngIf="busy"></ion-spinner></button>\n  <ion-input type="file" (change)="changeListener($event)" *ngIf="settingsService.remoteSettings.restricted"></ion-input>\n</ion-footer>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/chat/chat.html"*/,
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

/***/ 223:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return CompleteTestService; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__settings_service__ = __webpack_require__(22);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__bulletinSecret_service__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__angular_http__ = __webpack_require__(21);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4_rxjs_add_operator_map__ = __webpack_require__(656);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4_rxjs_add_operator_map___default = __webpack_require__.n(__WEBPACK_IMPORTED_MODULE_4_rxjs_add_operator_map__);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__graph_service__ = __webpack_require__(26);
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
    function CompleteTestService(http, settingsService, bulletinSecretService, graphService) {
        this.http = http;
        this.settingsService = settingsService;
        this.bulletinSecretService = bulletinSecretService;
        this.graphService = graphService;
        this.labelAttribute = "name";
        this.formValueAttribute = "value";
    }
    CompleteTestService.prototype.getResults = function (searchTerm) {
        return this.graphService.graph.friends.map(function (item) {
            var value = {
                username: item.relationship.identity.username,
                username_signature: item.relationship.identity.username_signature,
                public_key: item.relationship.identity.public_key
            };
            return { name: item.relationship.identity.username, value: value };
        });
    };
    CompleteTestService = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["B" /* Injectable */])(),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_3__angular_http__["b" /* Http */],
            __WEBPACK_IMPORTED_MODULE_1__settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_2__bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_5__graph_service__["a" /* GraphService */]])
    ], CompleteTestService);
    return CompleteTestService;
}());

//# sourceMappingURL=autocomplete.provider.js.map

/***/ }),

/***/ 224:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return FirebaseService; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__ionic_native_firebase__ = __webpack_require__(386);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__graph_service__ = __webpack_require__(26);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__settings_service__ = __webpack_require__(22);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__angular_http__ = __webpack_require__(21);
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

/***/ 225:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return MailItemPage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(9);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__app_bulletinSecret_service__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_graph_service__ = __webpack_require__(26);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_transaction_service__ = __webpack_require__(29);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_wallet_service__ = __webpack_require__(24);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__compose__ = __webpack_require__(134);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__profile_profile__ = __webpack_require__(62);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};








var MailItemPage = /** @class */ (function () {
    function MailItemPage(navCtrl, navParams, walletService, graphService, bulletinSecretService, alertCtrl, transactionService) {
        this.navCtrl = navCtrl;
        this.navParams = navParams;
        this.walletService = walletService;
        this.graphService = graphService;
        this.bulletinSecretService = bulletinSecretService;
        this.alertCtrl = alertCtrl;
        this.transactionService = transactionService;
        this.item = navParams.data.item;
    }
    MailItemPage.prototype.replyMail = function (item) {
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_6__compose__["a" /* ComposePage */], {
            item: item,
            mode: 'reply',
            thread: item.thread || item.id,
            message_type: item.message_type
        });
    };
    MailItemPage.prototype.replyToAllMail = function (item) {
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_6__compose__["a" /* ComposePage */], {
            item: item,
            mode: 'replyToAll',
            thread: item.thread || item.id,
            message_type: item.message_type
        });
    };
    MailItemPage.prototype.forwardMail = function (item) {
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_6__compose__["a" /* ComposePage */], {
            item: item,
            mode: 'forward'
        });
    };
    MailItemPage.prototype.signMail = function (item) {
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_6__compose__["a" /* ComposePage */], {
            item: item,
            mode: 'sign',
            thread: item.thread || item.id
        });
    };
    MailItemPage.prototype.addToCalendar = function (item) {
        var _this = this;
        var alert = this.alertCtrl.create();
        alert.setTitle('Send mail confirmation');
        alert.setSubTitle('Are you sure?');
        alert.addButton('Cancel');
        alert.addButton({
            text: 'Confirm',
            handler: function (data) {
                _this.walletService.get()
                    .then(function () {
                    var rid = _this.graphService.generateRid(_this.bulletinSecretService.identity.username_signature, _this.bulletinSecretService.identity.username_signature, 'event_meeting');
                    return _this.transactionService.generateTransaction({
                        relationship: {
                            event: {
                                sender: _this.item.sender,
                                subject: _this.item.subject,
                                body: _this.item.body,
                                thread: _this.item.thread,
                                message_type: _this.item.message_type,
                                event_datetime: _this.item.event_datetime
                            }
                        },
                        rid: rid
                    });
                }).then(function (txn) {
                    return _this.transactionService.sendTransaction();
                }).then(function () {
                    _this.navCtrl.pop();
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
    MailItemPage.prototype.addFriend = function () {
        var _this = this;
        var info;
        var buttons = [];
        buttons.push({
            text: 'Add',
            handler: function (data) {
                return _this.graphService.addFriend(_this.item.sender)
                    .then(function (txn) {
                    var alert = _this.alertCtrl.create();
                    alert.setTitle('Contact Request Sent');
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
        alert.setTitle('Add contact');
        alert.setSubTitle('Do you want to add ' + this.item.sender.username + '?');
        alert.present();
    };
    MailItemPage.prototype.viewProfile = function (identity) {
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_7__profile_profile__["a" /* ProfilePage */], {
            identity: identity
        });
    };
    MailItemPage.prototype.toHex = function (byteArray) {
        var callback = function (byte) {
            return ('0' + (byte & 0xFF).toString(16)).slice(-2);
        };
        return Array.from(byteArray, callback).join('');
    };
    MailItemPage = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["n" /* Component */])({
            selector: 'mail-item',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/mail/mailitem.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n    <ion-title>{{item.subject}}</ion-title>\n  </ion-navbar>\n</ion-header>\n<ion-content padding>\n  <button ion-button secondary (click)="replyMail(item)" *ngIf="graphService.isAdded(item.sender)">Reply</button>\n  <button ion-button secondary (click)="addFriend(item)" *ngIf="!graphService.isAdded(item.sender)">Add sender as contact</button>\n  <button *ngIf="item.group" ion-button secondary (click)="replyToAllMail(item)">Reply to all</button>\n  <button ion-button secondary (click)="forwardMail(item)">Forward</button>\n  <button *ngIf="item.message_type == \'contract\'" ion-button secondary (click)="signMail(item)">Sign</button>\n  <button *ngIf="item.message_type == \'event_meeting\'" ion-button secondary (click)="addToCalendar(item)">Add to calendar</button>\n  <div title="Verified" class="sender">\n    <span (click)="viewProfile(item.sender)">{{item.sender.username}} <ion-icon name="checkmark-circle" class="success"></ion-icon></span>\n    <span *ngIf="item.group" (click)="viewProfile(item.group)">{{item.group.username}} <ion-icon name="checkmark-circle" class="success"></ion-icon></span>\n  </div>\n  <div *ngIf="item.message_type == \'contract_signed\'"><strong>Contract signed</strong> <ion-icon name="checkmark-circle" class="success"></ion-icon></div>\n  <ion-item>{{item.datetime}}</ion-item>\n  <ion-item *ngIf="item.event_datetime">{{item.event_datetime}}</ion-item>\n  <ion-item><pre>{{item.body}}</pre></ion-item>\n  <ion-item *ngIf="item.skylink"><a href="https://centeridentity.com/skynet/skylink/{{item.skylink}}" target="_blank">Download {{item.filename}}</a></ion-item>\n</ion-content>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/mail/mailitem.html"*/
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["i" /* NavController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["j" /* NavParams */],
            __WEBPACK_IMPORTED_MODULE_5__app_wallet_service__["a" /* WalletService */],
            __WEBPACK_IMPORTED_MODULE_3__app_graph_service__["a" /* GraphService */],
            __WEBPACK_IMPORTED_MODULE_2__app_bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["a" /* AlertController */],
            __WEBPACK_IMPORTED_MODULE_4__app_transaction_service__["a" /* TransactionService */]])
    ], MailItemPage);
    return MailItemPage;
}());

//# sourceMappingURL=mailitem.js.map

/***/ }),

/***/ 226:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return SiaFiles; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(9);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__app_wallet_service__ = __webpack_require__(24);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_transaction_service__ = __webpack_require__(29);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_opengraphparser_service__ = __webpack_require__(135);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_settings_service__ = __webpack_require__(22);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_bulletinSecret_service__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__angular_http__ = __webpack_require__(21);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__app_graph_service__ = __webpack_require__(26);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__profile_profile__ = __webpack_require__(62);
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
    function SiaFiles(navParams, viewCtrl, walletService, alertCtrl, transactionService, openGraphParserService, settingsService, bulletinSecretService, ahttp, graphService, navCtrl, events) {
        this.navParams = navParams;
        this.viewCtrl = viewCtrl;
        this.walletService = walletService;
        this.alertCtrl = alertCtrl;
        this.transactionService = transactionService;
        this.openGraphParserService = openGraphParserService;
        this.settingsService = settingsService;
        this.bulletinSecretService = bulletinSecretService;
        this.ahttp = ahttp;
        this.graphService = graphService;
        this.navCtrl = navCtrl;
        this.events = events;
        this.logicalParent = null;
        this.mode = '';
        this.postText = null;
        this.post = {};
        this.files = null;
        this.selectedFile = null;
        this.group = null;
        this.error = '';
        this.group = navParams.data.group;
        this.mode = navParams.data.mode || 'page';
        this.logicalParent = navParams.data.logicalParent;
        var files = [];
        for (var i = 0; i < this.graphService.graph.files.length; i++) {
            var file = this.graphService.graph.files[i];
            files.push({
                title: 'Messages',
                label: file.relationship.username,
                component: __WEBPACK_IMPORTED_MODULE_9__profile_profile__["a" /* ProfilePage */],
                count: false,
                color: '',
                kwargs: { identity: file.relationship },
                root: false
            });
        }
        this.events.publish('menuonly', files);
    }
    SiaFiles.prototype.changeListener = function ($event) {
        var _this = this;
        this.filepath = $event.target.files[0].name;
        var reader = new FileReader();
        reader.readAsDataURL($event.target.files[0]);
        reader.onload = function () {
            _this.filedata = reader.result.toString().substr(22);
        };
        reader.onerror = function () { };
    };
    SiaFiles.prototype.upload = function () {
        var _this = this;
        this.ahttp.post(this.settingsService.remoteSettings['baseUrl'] + '/sia-upload?filename=' + encodeURIComponent(this.filepath), { file: this.filedata })
            .subscribe(function (res) {
            var data = res.json();
            if (!data.skylink)
                return;
            _this.graphService.createGroup(_this.filepath, null, { skylink: data.skylink }, 'file');
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
                                my_username_signature: _this.bulletinSecretService.generate_username_signature(),
                                my_username: _this.bulletinSecretService.username
                            },
                            username_signature: _this.group.username_signature,
                            rid: _this.group.rid,
                            requester_rid: _this.group.requester_rid,
                            requested_rid: _this.group.requested_rid
                        })
                            .then(function () {
                            resolve();
                        })
                            .catch(function (err) {
                            reject('failed generating transaction');
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
                            reject(err);
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
    SiaFiles.prototype.openProfile = function (item) {
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_9__profile_profile__["a" /* ProfilePage */], {
            identity: item.relationship,
        });
    };
    SiaFiles.prototype.import = function () {
        var _this = this;
        var buttons = [];
        buttons.push({
            text: 'Import',
            handler: function (data) {
                var identity = JSON.parse(data.identity);
                _this.graphService.addGroup(identity, null, null, null);
            }
        });
        var alert = this.alertCtrl.create({
            inputs: [
                {
                    name: 'identity',
                    placeholder: 'Paste file code...'
                }
            ],
            buttons: buttons
        });
        alert.setTitle('Import file');
        alert.setSubTitle('Paste the code of your file below');
        alert.present();
    };
    SiaFiles.prototype.dismiss = function () {
        this.logicalParent.refresh();
        this.viewCtrl.dismiss();
    };
    SiaFiles = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["n" /* Component */])({
            selector: 'modal-files',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/siafiles/siafiles.html"*/'<ion-header>\n  <ion-toolbar>\n    <ion-title>\n      Files\n    </ion-title>\n    <ion-buttons start *ngIf="mode == \'modal\'">\n      <button ion-button (click)="dismiss()">\n        <span ion-text color="primary" showWhen="ios">Cancel</span>\n        <ion-icon name="md-close" showWhen="android,windows,core"></ion-icon>\n      </button>\n    </ion-buttons>\n  </ion-toolbar>\n</ion-header>\n<ion-content>\n  <ion-item *ngIf="mode == \'modal\' && !error">\n    <ion-label>Files</ion-label>\n    <ion-select [(ngModel)]="selectedFile">\n      <ion-option *ngFor="let file of files" value="{{file.siapath}}">{{file.siapath}}</ion-option>\n    </ion-select>\n  </ion-item>\n  <ion-item>\n    <ion-label id="profile_image" color="primary"></ion-label>\n    <ion-input type="file" (change)="changeListener($event)"></ion-input>\n  </ion-item>\n  <ion-item *ngIf="!error">\n    <button ion-button secondary (click)="upload()" *ngIf="mode == \'page\' && !error" [disabled]="!filepath">Upload</button>\n  </ion-item>\n  <ion-item>\n    <button ion-button secondary (click)="import()">Import</button>\n  </ion-item>\n  <button ion-button secondary (click)="submit()" *ngIf="mode == \'modal\'">Post</button>\n  <ion-card *ngIf="post.title">\n    <img src="{{post.image}}" *ngIf="post.image" />\n    <ion-card-content>\n      <ion-card-title>\n        {{post.title}}\n      </ion-card-title>\n      <p *ngIf="post.description">\n        {{post.description}}\n      </p>\n    </ion-card-content>\n  </ion-card>\n  <ion-item *ngIf="error">You must download the <a href="https://github.com/pdxwebdev/yadacoin/releases/latest" target="_blank">full node</a> to store and share files.</ion-item>\n</ion-content>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/siafiles/siafiles.html"*/
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["j" /* NavParams */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["m" /* ViewController */],
            __WEBPACK_IMPORTED_MODULE_2__app_wallet_service__["a" /* WalletService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["a" /* AlertController */],
            __WEBPACK_IMPORTED_MODULE_3__app_transaction_service__["a" /* TransactionService */],
            __WEBPACK_IMPORTED_MODULE_4__app_opengraphparser_service__["a" /* OpenGraphParserService */],
            __WEBPACK_IMPORTED_MODULE_5__app_settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_6__app_bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_7__angular_http__["b" /* Http */],
            __WEBPACK_IMPORTED_MODULE_8__app_graph_service__["a" /* GraphService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["i" /* NavController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["b" /* Events */]])
    ], SiaFiles);
    return SiaFiles;
}());

//# sourceMappingURL=siafiles.js.map

/***/ }),

/***/ 24:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return WalletService; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__bulletinSecret_service__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__settings_service__ = __webpack_require__(22);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__angular_http__ = __webpack_require__(21);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4_rxjs_operators__ = __webpack_require__(51);
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
        this.wallet = {
            balance: 0,
            unspent_transactions: []
        };
    }
    WalletService.prototype.get = function (amount_needed) {
        var _this = this;
        if (amount_needed === void 0) { amount_needed = 0; }
        return new Promise(function (resolve, reject) {
            if (!_this.settingsService.remoteSettings || !_this.settingsService.remoteSettings['walletUrl'])
                return resolve();
            return _this.walletPromise(amount_needed)
                .then(function () {
                return resolve();
            })
                .catch(function (err) {
                return reject(err);
            });
        });
    };
    WalletService.prototype.walletPromise = function (amount_needed) {
        var _this = this;
        if (amount_needed === void 0) { amount_needed = 0; }
        return new Promise(function (resolve, reject) {
            if (!_this.settingsService.remoteSettings['walletUrl']) {
                return reject('no wallet url');
            }
            if (_this.bulletinSecretService.username) {
                var headers = new __WEBPACK_IMPORTED_MODULE_3__angular_http__["a" /* Headers */]();
                headers.append('Authorization', 'Bearer ' + _this.settingsService.tokens[_this.bulletinSecretService.keyname]);
                var options = new __WEBPACK_IMPORTED_MODULE_3__angular_http__["d" /* RequestOptions */]({ headers: headers, withCredentials: true });
                _this.ahttp.get(_this.settingsService.remoteSettings['walletUrl'] + '?amount_needed=' + amount_needed + '&address=' + _this.bulletinSecretService.key.getAddress() + '&username_signature=' + _this.bulletinSecretService.username_signature + '&origin=' + window.location.origin, options)
                    .pipe(Object(__WEBPACK_IMPORTED_MODULE_4_rxjs_operators__["timeout"])(30000))
                    .subscribe(function (data) {
                    if (data['_body']) {
                        _this.walletError = false;
                        _this.wallet = JSON.parse(data['_body']);
                        _this.wallet.balance = parseFloat(_this.wallet.balance); //pasefloat
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

/***/ 257:
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
webpackEmptyAsyncContext.id = 257;

/***/ }),

/***/ 26:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* WEBPACK VAR INJECTION */(function(Buffer) {/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return GraphService; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__ionic_storage__ = __webpack_require__(42);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__bulletinSecret_service__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__transaction_service__ = __webpack_require__(29);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__settings_service__ = __webpack_require__(22);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__ionic_native_badge__ = __webpack_require__(379);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__angular_http__ = __webpack_require__(21);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7_ionic_angular__ = __webpack_require__(9);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8_rxjs_operators__ = __webpack_require__(51);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__ionic_native_geolocation__ = __webpack_require__(219);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_10__wallet_service__ = __webpack_require__(24);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_11_eciesjs__ = __webpack_require__(342);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_11_eciesjs___default = __webpack_require__.n(__WEBPACK_IMPORTED_MODULE_11_eciesjs__);
var __assign = (this && this.__assign) || function () {
    __assign = Object.assign || function(t) {
        for (var s, i = 1, n = arguments.length; i < n; i++) {
            s = arguments[i];
            for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p))
                t[p] = s[p];
        }
        return t;
    };
    return __assign.apply(this, arguments);
};
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
    function GraphService(storage, bulletinSecretService, settingsService, badge, platform, ahttp, transactionService, geolocation, walletService) {
        this.storage = storage;
        this.bulletinSecretService = bulletinSecretService;
        this.settingsService = settingsService;
        this.badge = badge;
        this.platform = platform;
        this.ahttp = ahttp;
        this.transactionService = transactionService;
        this.geolocation = geolocation;
        this.walletService = walletService;
        this.graph = {
            messages: [],
            friends: [],
            groups: [],
            files: [],
            mail: []
        };
        this.getGraphError = false;
        this.getSentFriendRequestsError = false;
        this.getGroupsRequestsError = false;
        this.getFriendRequestsError = false;
        this.getFriendsError = false;
        this.getMessagesError = false;
        this.getMailError = false;
        this.getNewMessagesError = false;
        this.getSignInsError = false;
        this.getNewSignInsError = false;
        this.getPostsError = false;
        this.getReactsError = false;
        this.getCommentsError = false;
        this.getcommentReactsError = false;
        this.getcommentRepliesError = false;
        this.getCalendarError = false;
        this.usernames = {};
        this.username_signature = '';
        this.groups_indexed = {};
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
        this.friends_indexed = {};
    }
    GraphService.prototype.resetGraph = function () {
        this.graph = {
            messages: [],
            friends: [],
            groups: [],
            files: [],
            mail: []
        };
        this.groups_indexed = {};
        this.friends_indexed = {};
    };
    GraphService.prototype.refreshFriendsAndGroups = function () {
        var _this = this;
        this.resetGraph();
        return this.getGroups()
            .then(function () {
            return _this.getGroups(null, 'file');
        })
            .then(function () {
            return _this.getFriendRequests();
        });
    };
    GraphService.prototype.endpointRequest = function (endpoint, ids, rids, post_data) {
        var _this = this;
        if (ids === void 0) { ids = null; }
        if (rids === void 0) { rids = null; }
        if (post_data === void 0) { post_data = null; }
        return new Promise(function (resolve, reject) {
            var headers = new __WEBPACK_IMPORTED_MODULE_6__angular_http__["a" /* Headers */]();
            headers.append('Authorization', 'Bearer ' + _this.settingsService.tokens[_this.bulletinSecretService.keyname]);
            var options = new __WEBPACK_IMPORTED_MODULE_6__angular_http__["d" /* RequestOptions */]({ headers: headers, withCredentials: true });
            var promise = null;
            if (ids) {
                promise = _this.ahttp.post(_this.settingsService.remoteSettings['graphUrl'] + '/' + endpoint + '?origin=' + encodeURIComponent(window.location.origin) + '&username_signature=' + encodeURIComponent(_this.bulletinSecretService.username_signature), { ids: ids }, options);
            }
            else if (rids) {
                promise = _this.ahttp.post(_this.settingsService.remoteSettings['graphUrl'] + '/' + endpoint + '?origin=' + encodeURIComponent(window.location.origin) + '&username_signature=' + encodeURIComponent(_this.bulletinSecretService.username_signature), { rids: rids }, options);
            }
            else if (post_data) {
                promise = _this.ahttp.post(_this.settingsService.remoteSettings['graphUrl'] + '/' + endpoint + '?origin=' + encodeURIComponent(window.location.origin) + '&username_signature=' + encodeURIComponent(_this.bulletinSecretService.username_signature), post_data, options);
            }
            else {
                promise = _this.ahttp.get(_this.settingsService.remoteSettings['graphUrl'] + '/' + endpoint + '?origin=' + encodeURIComponent(window.location.origin) + '&username_signature=' + encodeURIComponent(_this.bulletinSecretService.username_signature), options);
            }
            promise
                .pipe(Object(__WEBPACK_IMPORTED_MODULE_8_rxjs_operators__["timeout"])(30000))
                .subscribe(function (data) {
                try {
                    var info = data.json();
                    _this.graph.rid = info.rid;
                    _this.graph.username_signature = info.username_signature;
                    _this.graph.registered = info.registered;
                    _this.graph.pending_registration = info.pending_registration;
                    resolve(info);
                }
                catch (err) {
                    console.log(err);
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
            _this.endpointRequest('get-graph-sent-friend-requests', null, [_this.generateRid(_this.bulletinSecretService.identity.username_signature, _this.bulletinSecretService.identity.username_signature)])
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
            _this.endpointRequest('get-graph-collection', null, [_this.generateRid(_this.bulletinSecretService.identity.username_signature, _this.bulletinSecretService.identity.username_signature)])
                .then(function (data) {
                _this.parseFriendRequests(data.collection);
                _this.getFriendRequestsError = false;
                resolve();
            }).catch(function (err) {
                _this.getFriendRequestsError = true;
                reject(err);
            }).catch(function (err) {
                reject(err);
            });
        });
    };
    GraphService.prototype.getFriends = function (ignoreCache) {
        var _this = this;
        if (ignoreCache === void 0) { ignoreCache = false; }
        if (this.graph.friends && this.graph.friends.length > 0 && !ignoreCache) {
            return new Promise(function (resolve, reject) { return resolve(null); });
        }
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
    GraphService.prototype.getGroups = function (rid, collectionName, ignoreCache) {
        var _this = this;
        if (rid === void 0) { rid = null; }
        if (collectionName === void 0) { collectionName = 'group'; }
        if (ignoreCache === void 0) { ignoreCache = false; }
        var root = !rid;
        rid = rid || this.generateRid(this.bulletinSecretService.identity.username_signature, this.bulletinSecretService.identity.username_signature, collectionName);
        if (this.graph[collectionName + 's'] && this.graph[collectionName + 's'].length > 0 && !ignoreCache) {
            return new Promise(function (resolve, reject) { return resolve(null); });
        }
        return this.endpointRequest('get-graph-collection', null, rid)
            .then(function (data) {
            return _this.parseGroups(data.collection, root, collectionName + 's');
        }).then(function (groups) {
            _this.getGroupsRequestsError = false;
        });
    };
    GraphService.prototype.getMail = function (rid) {
        var _this = this;
        //get messages for a specific friend
        return new Promise(function (resolve, reject) {
            _this.endpointRequest('get-graph-collection', null, rid)
                .then(function (data) {
                return _this.parseMail(data.collection, 'new_mail_counts', 'new_mail_count', undefined, 'envelope', 'last_mail_height');
            })
                .then(function (mail) {
                _this.graph.mail = mail;
                _this.graph.mail.sort(function (a, b) {
                    if (parseInt(a.time) > parseInt(b.time))
                        return -1;
                    if (parseInt(a.time) < parseInt(b.time))
                        return 1;
                    return 0;
                });
                _this.getMailError = false;
                return resolve(mail);
            }).catch(function (err) {
                _this.getMailError = true;
                reject(err);
            });
        });
    };
    GraphService.prototype.getSentMail = function (rid) {
        var _this = this;
        //get messages for a specific friend
        return new Promise(function (resolve, reject) {
            _this.endpointRequest('get-graph-collection', null, [rid])
                .then(function (data) {
                return _this.parseMail(data.collection, 'new_sent_mail_counts', 'new_sent_mail_count', undefined, 'envelope', 'last_sent_mail_height');
            })
                .then(function (mail) {
                _this.graph.mail = mail;
                _this.graph.mail.sort(function (a, b) {
                    if (parseInt(a.time) > parseInt(b.time))
                        return -1;
                    if (parseInt(a.time) < parseInt(b.time))
                        return 1;
                    return 0;
                });
                _this.getMailError = false;
                return resolve(mail);
            }).catch(function (err) {
                _this.getMailError = true;
                reject(err);
            });
        });
    };
    GraphService.prototype.getMessages = function (rid) {
        var _this = this;
        if (typeof rid === 'string')
            rid = [rid];
        //get messages for a specific friend
        return new Promise(function (resolve, reject) {
            _this.endpointRequest('get-graph-collection', null, rid)
                .then(function (data) {
                return _this.parseMessages(data.collection, 'new_messages_counts', 'new_messages_count', rid, 'chatText', 'last_message_height');
            })
                .then(function (chats) {
                _this.graph.messages = chats;
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
    GraphService.prototype.getSentMessages = function () {
        var _this = this;
        //get sent messages
        return new Promise(function (resolve, reject) {
            _this.endpointRequest('get-graph-sent-messages', null, [])
                .then(function (data) {
                return _this.parseMessages(data.messages, 'sent_messages_counts', 'sent_messages_count', null, 'chatText', 'last_message_height');
            })
                .then(function (chats) {
                // if (!this.graph.messages) {
                //     this.graph.messages = {};
                // }
                // if (chats[rid]){
                //     this.graph.messages[rid] = chats[rid];
                //     this.graph.messages[rid].sort(function (a, b) {
                //         if (parseInt(a.time) > parseInt(b.time))
                //         return 1
                //         if ( parseInt(a.time) < parseInt(b.time))
                //         return -1
                //         return 0
                //     });
                // }
                // this.getMessagesError = false;
                // return resolve(chats[rid]);
            }).catch(function (err) {
                _this.getMessagesError = true;
                reject(err);
            });
        });
    };
    GraphService.prototype.getGroupMessages = function (key, requested_rid, rid) {
        var _this = this;
        //get messages for a specific friend
        var choice_rid = requested_rid || rid;
        return new Promise(function (resolve, reject) {
            _this.endpointRequest('get-graph-collection', null, [choice_rid])
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
    GraphService.prototype.getCalendar = function (rids) {
        var _this = this;
        return this.endpointRequest('get-graph-collection', undefined, rids)
            .then(function (data) {
            _this.graph.calendar = _this.parseCalendar(data.collection);
            _this.getCalendarError = false;
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
            try {
                var decrypted = this.publicDecrypt(sent_friend_request['relationship']);
                var relationship = JSON.parse(decrypted);
                if (!relationship.identity.username)
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
                delete sent_friend_requestsObj[sent_friend_request.rid];
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
        var sent_friend_requestsObj = {};
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
            try {
                var decrypted = this.publicDecrypt(friend_request.relationship);
                var relationship = JSON.parse(decrypted);
                this.graph.friends.push(friend_request);
                friend_request.relationship = relationship;
                this.friends_indexed[friend_request.rid] = friend_request;
                if (sent_friend_requestsObj[friend_request.rid]) {
                    delete friend_requestsObj[friend_request.rid];
                    delete sent_friend_requestsObj[friend_request.rid];
                }
                else {
                    friend_requestsObj[friend_request.rid] = friend_request;
                }
                if (this.keys[friend_request.rid].dh_private_keys.indexOf(relationship.dh_private_key) === -1 && relationship.dh_private_key) {
                    this.keys[friend_request.rid].dh_private_keys.push(relationship.dh_private_key);
                }
            }
            catch (err) {
                if (friend_requestsObj[friend_request.rid]) {
                    delete friend_requestsObj[friend_request.rid];
                    delete sent_friend_requestsObj[friend_request.rid];
                }
                else {
                    sent_friend_requestsObj[friend_request.rid] = friend_request;
                }
                if (this.keys[friend_request.rid].dh_public_keys.indexOf(friend_request.dh_public_key) === -1 && friend_request.dh_public_key) {
                    this.keys[friend_request.rid].dh_public_keys.push(friend_request.dh_public_key);
                }
            }
        }
        var arr_sent_friend_requests = [];
        for (var i_2 in sent_friend_requestsObj) {
            arr_sent_friend_requests.push(sent_friend_requestsObj[i_2].rid);
        }
        this.sent_friend_requests_indexed = {};
        var sent_friend_requests = [];
        var sent_friend_requests_diff = new Set(arr_sent_friend_requests);
        if (arr_sent_friend_requests.length > 0) {
            var arr_sent_friend_request_keys = Array.from(sent_friend_requests_diff.keys());
            for (i = 0; i < arr_sent_friend_request_keys.length; i++) {
                sent_friend_requests.push(sent_friend_requestsObj[arr_sent_friend_request_keys[i]]);
                this.sent_friend_requests_indexed[arr_sent_friend_request_keys[i]] = sent_friend_requestsObj[arr_sent_friend_request_keys[i]];
            }
        }
        var arr_friend_requests = [];
        for (var i_3 in friend_requestsObj) {
            arr_friend_requests.push(friend_requestsObj[i_3].rid);
        }
        friend_requests = [];
        var friend_requests_diff = new Set(arr_friend_requests);
        if (arr_friend_requests.length > 0) {
            var arr_friend_request_keys = Array.from(friend_requests_diff.keys());
            for (i = 0; i < arr_friend_request_keys.length; i++) {
                friend_requests.push(this.friends_indexed[arr_friend_request_keys[i]]);
            }
        }
        this.friend_request_count = friend_requests.length;
        if (this.platform.is('android') || this.platform.is('ios')) {
            this.badge.set(friend_requests.length);
        }
        this.graph.friend_requests = friend_requests;
        this.graph.sent_friend_requests = sent_friend_requests;
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
                    friendsObj[friend.rid] = { friend: friend };
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
                delete friendsObj[sent_friend_request.rid];
                if (secrets_rids.indexOf(sent_friend_request.rid) >= 0) {
                    if (!friendsObj[sent_friend_request.rid])
                        friendsObj[sent_friend_request.rid] = {};
                    friendsObj[sent_friend_request.rid].sent_friend_request = sent_friend_request;
                }
            }
            for (i = 0; i < _this.graph.friend_requests.length; i++) {
                var friend_request = _this.graph.friend_requests[i];
                delete friendsObj[friend_request.rid];
                if (secrets_rids.indexOf(friend_request.rid) >= 0) {
                    if (!friendsObj[friend_request.rid])
                        friendsObj[friend_request.rid] = {};
                    friendsObj[friend_request.rid] = friend_request;
                }
            }
            var arr_friends = Object.keys(friendsObj);
            friends = [];
            var friends_diff = new Set(arr_friends);
            if (arr_friends.length > 0) {
                var arr_friends_keys = Array.from(friends_diff.keys());
                for (i = 0; i < arr_friends_keys.length; i++) {
                    friends.push(friendsObj[arr_friends_keys[i]].friend_request || friendsObj[arr_friends_keys[i]].friend);
                }
            }
            resolve(friends);
        });
    };
    GraphService.prototype.parseGroups = function (groups, root, collectionName) {
        var _this = this;
        if (root === void 0) { root = true; }
        if (collectionName === void 0) { collectionName = 'group'; }
        // we must call getSentFriendRequests and getFriendRequests before getting here
        // because we need this.keys to be populated with the dh_public_keys and dh_private_keys from the requests
        // though friends really should be cached
        // should be key: shared-secret_rid|pub_key[:26]priv_key[:26], value: {shared_secret: <shared_secret>, friend: [transaction.dh_public_key, transaction.dh_private_key]}
        return new Promise(function (resolve, reject) {
            //start "just do dedup yada server because yada server adds itself to the friends array automatically straight from the api"
            var promises = [];
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
                var failed = false;
                try {
                    if (typeof group.relationship == 'object') {
                        bypassDecrypt = true;
                    }
                    else {
                        decrypted = _this.decrypt(group.relationship);
                    }
                    var relationship;
                    if (!bypassDecrypt) {
                        relationship = JSON.parse(decrypted);
                        group['relationship'] = relationship;
                    }
                }
                catch (err) {
                    console.log(err);
                    failed = true;
                }
                if (failed && _this.groups_indexed[group.requester_rid]) {
                    try {
                        if (typeof group.relationship == 'object') {
                            bypassDecrypt = true;
                        }
                        else {
                            decrypted = _this.shared_decrypt(_this.groups_indexed[group.requester_rid].relationship.username_signature, group.relationship);
                        }
                        var relationship;
                        if (!bypassDecrypt) {
                            relationship = JSON.parse(decrypted);
                            group['relationship'] = relationship;
                        }
                    }
                    catch (err) {
                        console.log(err);
                        continue;
                    }
                }
                else if (failed && !_this.groups_indexed[group.requester_rid]) {
                    continue;
                }
                if (!_this.groups_indexed[group.requested_rid]) {
                    _this.graph[collectionName].push(group);
                }
                _this.groups_indexed[group.requested_rid] = group;
                if (group.relationship.wif) {
                    var key = foobar.bitcoin.ECPair.fromWIF(group.relationship.wif);
                    group.relationship.public_key = key.getPublicKeyBuffer().toString('hex');
                    group.relationship.username_signature = foobar.base64.fromByteArray(key.sign(foobar.bitcoin.crypto.sha256(group.relationship.username)).toDER());
                }
                _this.groups_indexed[_this.generateRid(relationship.username_signature, relationship.username_signature, 'group_mail')] = group;
                _this.groups_indexed[_this.generateRid(relationship.username_signature, relationship.username_signature, 'event_meeting')] = group;
                _this.groups_indexed[_this.generateRid(relationship.username_signature, relationship.username_signature, relationship.username_signature)] = group;
                try {
                    promises.push(_this.getGroups(_this.generateRid(relationship.username_signature, relationship.username_signature, relationship.username_signature)));
                }
                catch (err) {
                    console.log(err);
                }
            }
            var arr_friends = Object.keys(_this.groups_indexed);
            groups = [];
            var friends_diff = new Set(arr_friends);
            if (arr_friends.length > 0) {
                var used_username_signatures = [];
                var arr_friends_keys = Array.from(friends_diff.keys());
                for (i = 0; i < arr_friends_keys.length; i++) {
                    if (used_username_signatures.indexOf(_this.groups_indexed[arr_friends_keys[i]].relationship.username_signature) > -1) {
                        continue;
                    }
                    else {
                        groups.push(_this.groups_indexed[arr_friends_keys[i]]);
                        used_username_signatures.push(_this.groups_indexed[arr_friends_keys[i]].relationship.username_signature);
                    }
                }
            }
            Promise.all(promises)
                .then(function () {
                return resolve(groups);
            });
        });
    };
    GraphService.prototype.parseMail = function (messages, graphCounts, graphCount, rid, messageType, messageHeightType) {
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
                var chats = [];
                dance: for (var i = 0; i < messages.length; i++) {
                    var message = messages[i];
                    if (!rid && chats[message.rid])
                        continue;
                    if (!message.rid)
                        continue;
                    if (message.dh_public_key)
                        continue;
                    //hopefully we've prepared the stored_secrets option before getting here
                    //by calling getSentFriendRequests and getFriendRequests
                    if (_this.groups_indexed[message.requested_rid]) {
                        try {
                            var decrypted = _this.shared_decrypt(_this.groups_indexed[message.requested_rid].relationship.username_signature, message.relationship);
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
                            messages[message.requested_rid] = message;
                            try {
                                message.relationship[messageType] = JSON.parse(Base64.decode(messageJson[messageType]));
                                message.relationship.isInvite = true;
                            }
                            catch (err) {
                                //not an invite, do nothing
                            }
                            chats.push(message);
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
                    else {
                        if (!_this.stored_secrets[message.rid])
                            continue;
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
                                messages[message.rid] = message;
                                try {
                                    message.relationship[messageType] = JSON.parse(Base64.decode(messageJson[messageType]));
                                    message.relationship.isInvite = true;
                                }
                                catch (err) {
                                    //not an invite, do nothing
                                }
                                chats.push(message);
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
                }
                resolve(chats);
            });
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
                    if (rid && message.rid !== rid && rid.indexOf(message.rid) === -1 && rid.indexOf(message.requested_rid) === -1)
                        continue;
                    if (!message.rid && !message.requested_rid)
                        continue;
                    if (message.dh_public_key)
                        continue;
                    if (_this.groups_indexed[message.requested_rid]) {
                        try {
                            var decrypted = _this.shared_decrypt(_this.groups_indexed[message.requested_rid].relationship.username_signature, message.relationship);
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
                            messages[message.requested_rid] = message;
                            if (!chats[message.requested_rid]) {
                                chats[message.requested_rid] = [];
                            }
                            try {
                                message.relationship[messageType] = JSON.parse(Base64.decode(messageJson[messageType]));
                                message.relationship.isInvite = true;
                            }
                            catch (err) {
                                //not an invite, do nothing
                            }
                            chats[message.requested_rid].push(message);
                            if (_this[graphCounts][message.requested_rid]) {
                                if (message.height > _this[graphCounts][message.requested_rid]) {
                                    _this[graphCount]++;
                                    if (!_this[graphCounts][message.requested_rid]) {
                                        _this[graphCounts][message.requested_rid] = 0;
                                    }
                                    _this[graphCounts][message.requested_rid]++;
                                }
                            }
                            else {
                                _this[graphCounts][message.requested_rid] = 1;
                                _this[graphCount]++;
                            }
                        }
                        continue dance;
                    }
                    else {
                        if (!_this.stored_secrets[message.rid])
                            continue;
                        var shared_secret = _this.stored_secrets[message.rid][j];
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
                                messages[message.rid] = message;
                                if (!chats[message.rid]) {
                                    chats[message.rid] = [];
                                }
                                try {
                                    message.relationship[messageType] = JSON.parse(Base64.decode(messageJson[messageType]));
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
                }
                resolve(chats);
            });
        });
    };
    GraphService.prototype.parseNewMessages = function (messages, graphCounts, graphCount, heightType) {
        var _this = this;
        this[graphCount] = 0;
        this[graphCounts] = {};
        var public_key = this.bulletinSecretService.key.getPublicKeyBuffer().toString('hex');
        return new Promise(function (resolve, reject) {
            return _this.getMessageHeights(graphCounts, heightType)
                .then(function () {
                var new_messages = [];
                for (var i = 0; i < messages.length; i++) {
                    var message = messages[i];
                    if (message.public_key != public_key) {
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
    GraphService.prototype.parseCalendar = function (events) {
        var eventsOut = [];
        for (var i = 0; i < events.length; i++) {
            //hopefully we've prepared the stored_secrets option before getting here
            //by calling getSentFriendRequests and getFriendRequests
            var event_1 = events[i];
            var decrypted = void 0;
            try {
                if (this.groups_indexed[event_1.requested_rid]) {
                    decrypted = this.shared_decrypt(this.groups_indexed[event_1.requested_rid].relationship.username_signature, event_1.relationship);
                }
                else {
                    decrypted = this.decrypt(event_1.relationship);
                }
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
            if (messageJson.envelope) {
                event_1.relationship = messageJson;
                event_1.relationship.envelope.event_datetime = new Date(event_1.relationship.envelope.event_datetime);
            }
            else if (messageJson.event) {
                event_1.relationship = messageJson;
                event_1.relationship.event.event_datetime = new Date(event_1.relationship.event.event_datetime);
            }
            eventsOut.push(event_1);
        }
        return eventsOut;
    };
    GraphService.prototype.getSharedSecrets = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
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
    GraphService.prototype.createGroup = function (groupname, parentGroup, extraData, collectionName) {
        var _this = this;
        if (parentGroup === void 0) { parentGroup = null; }
        if (extraData === void 0) { extraData = {}; }
        if (collectionName === void 0) { collectionName = 'group'; }
        if (!groupname)
            return new Promise(function (resolve, reject) { reject('username missing'); });
        var key = foobar.bitcoin.ECPair.makeRandom();
        var wif = key.toWIF();
        var pubKey = key.getPublicKeyBuffer().toString('hex');
        var address = key.getAddress();
        var username_signature = foobar.base64.fromByteArray(key.sign(foobar.bitcoin.crypto.sha256(groupname)).toDER());
        var relationship = __assign({ username: groupname, wif: wif, collection: collectionName }, extraData);
        if (parentGroup) {
            relationship.parent = {
                username: parentGroup.relationship.username,
                username_signature: parentGroup.relationship.username_signature,
                public_key: parentGroup.relationship.public_key,
                collection: collectionName
            };
        }
        return this.transactionService.generateTransaction({
            relationship: relationship,
            to: this.bulletinSecretService.publicKeyToAddress(pubKey),
            requester_rid: this.generateRid(parentGroup ? parentGroup.relationship.username_signature : this.bulletinSecretService.identity.username_signature, parentGroup ? parentGroup.relationship.username_signature : this.bulletinSecretService.identity.username_signature, parentGroup ? parentGroup.relationship.username_signature : collectionName),
            requested_rid: this.generateRid(username_signature, username_signature, parentGroup ? parentGroup.relationship.username_signature : collectionName),
            rid: this.generateRid(this.bulletinSecretService.identity.username_signature, username_signature),
            group: true
        }).then(function (txn) {
            return _this.transactionService.sendTransaction();
        }).then(function () {
            return _this.getGroups(null, relationship.collection, true);
        });
    };
    GraphService.prototype.checkInvite = function (identity) {
        return this.endpointRequest('check-invite', null, null, { 'identity': identity });
    };
    GraphService.prototype.getUserType = function (identifier) {
        return this.endpointRequest('get-user-type', null, null, { 'identifier': identifier });
    };
    GraphService.prototype.generateRecovery = function (username) {
        var _this = this;
        return new Promise(function (resolve, reject) {
            return _this.geolocation.getCurrentPosition().then(function (resp) {
                var result = resp.coords.longitude + (resp.coords.latitude + username);
                var target = 0x00000fffffffffffffffffffffffffffffffffffffffffffffffffffffffffff;
                var rid;
                var password;
                for (var i = 0; i === i; i++) {
                    result = forge.sha256.create().update(result).digest().toHex();
                    if (parseInt(result, 16) < target && password) {
                        result = forge.sha256.create().update(result).digest().toHex();
                        rid = result;
                        break;
                    }
                    if (parseInt(result, 16) < target && !password) {
                        result = forge.sha256.create().update(result).digest().toHex();
                        password = result;
                    }
                }
                return resolve([rid, password, username]);
            }).catch(function (error) {
                console.log('Error getting location', error);
            });
        });
    };
    GraphService.prototype.createRecovery = function (username) {
        var _this = this;
        this.generateRecovery(username)
            .then(function (args) {
            var rid = args[0];
            var shared_secret = args[1];
            return new Promise(function (resolve, reject) {
                if (!username)
                    return reject('username missing');
                return _this.storage.get(_this.bulletinSecretService.keyname).then(function (wif) {
                    var key = foobar.bitcoin.ECPair.fromWIF(wif);
                    var pubKey = key.getPublicKeyBuffer().toString('hex');
                    var address = key.getAddress();
                    var username_signature = foobar.base64.fromByteArray(key.sign(foobar.bitcoin.crypto.sha256(username)).toDER());
                    resolve({
                        public_key: pubKey,
                        username_signature: username_signature,
                        username: username,
                        wif: wif,
                        rid: rid,
                        shared_key: shared_secret
                    });
                });
            });
        })
            .then(function (info) {
            return _this.transactionService.generateTransaction({
                relationship: {
                    username_signature: info.username_signature,
                    public_key: info.public_key,
                    username: info.username,
                    identity: _this.bulletinSecretService.identity,
                    wif: info.wif
                },
                to: _this.bulletinSecretService.publicKeyToAddress(info.public_key),
                rid: info.rid,
                shared_secret: info.shared_key
            });
        }).then(function (txn) {
            return _this.transactionService.sendTransaction();
        });
    };
    GraphService.prototype.generateRid = function (username_signature1, username_signature2, extra) {
        if (extra === void 0) { extra = ''; }
        var username_signatures = [username_signature1, username_signature2].sort(function (a, b) {
            return a.toLowerCase().localeCompare(b.toLowerCase());
        });
        return forge.sha256.create().update(username_signatures[0] + username_signatures[1] + extra).digest().toHex();
    };
    GraphService.prototype.addFriendFromSkylink = function (skylink) {
        var _this = this;
        return this.identityFromSkylink(skylink)
            .then(function (identity) {
            return _this.addFriend(identity);
        });
    };
    GraphService.prototype.addFriend = function (identity, rid, requester_rid, requested_rid) {
        var _this = this;
        if (rid === void 0) { rid = ''; }
        if (requester_rid === void 0) { requester_rid = ''; }
        if (requested_rid === void 0) { requested_rid = ''; }
        rid = rid || this.generateRid(this.bulletinSecretService.identity.username_signature, identity.username_signature);
        requester_rid = requester_rid || this.generateRid(this.bulletinSecretService.identity.username_signature, this.bulletinSecretService.identity.username_signature);
        requested_rid = requested_rid || this.generateRid(identity.username_signature, identity.username_signature);
        if (requester_rid && requested_rid) {
            // get rid from bulletin secrets
        }
        else {
            requester_rid = '';
            requested_rid = '';
        }
        var raw_dh_private_key = foobar.bitcoin.crypto.sha256(this.bulletinSecretService.key.toWIF() + identity.username_signature);
        var raw_dh_public_key = X25519.getPublic(raw_dh_private_key);
        var dh_private_key = this.toHex(raw_dh_private_key);
        var dh_public_key = this.toHex(raw_dh_public_key);
        return this.transactionService.generateTransaction({
            relationship: {
                dh_private_key: dh_private_key,
                identity: this.bulletinSecretService.identity
            },
            dh_public_key: dh_public_key,
            requested_rid: requested_rid,
            requester_rid: requester_rid,
            rid: rid,
            to: this.bulletinSecretService.publicKeyToAddress(identity.public_key),
            recipient_identity: identity
        }).then(function (hash) {
            return _this.transactionService.sendTransaction();
        }).then(function () {
            return _this.getFriends();
        });
    };
    GraphService.prototype.addGroupFromSkylink = function (skylink) {
        var _this = this;
        return this.identityFromSkylink(skylink)
            .then(function (identity) {
            return _this.addGroup(identity);
        });
    };
    GraphService.prototype.addGroup = function (identity, rid, requester_rid, requested_rid) {
        var _this = this;
        if (rid === void 0) { rid = ''; }
        if (requester_rid === void 0) { requester_rid = ''; }
        if (requested_rid === void 0) { requested_rid = ''; }
        identity.collection = identity.collection || 'group';
        rid = rid || this.generateRid(this.bulletinSecretService.identity.username_signature, identity.username_signature);
        requester_rid = requester_rid || this.generateRid(this.bulletinSecretService.identity.username_signature, this.bulletinSecretService.identity.username_signature, identity.collection);
        requested_rid = requested_rid || this.generateRid(identity.username_signature, identity.username_signature, identity.collection);
        if (requester_rid && requested_rid) {
            // get rid from bulletin secrets
        }
        else {
            requester_rid = '';
            requested_rid = '';
        }
        return this.transactionService.generateTransaction({
            rid: rid,
            relationship: identity,
            requested_rid: requested_rid,
            requester_rid: requester_rid,
            to: this.bulletinSecretService.publicKeyToAddress(identity.public_key)
        }).then(function (hash) {
            return _this.transactionService.sendTransaction();
        }).then(function () {
            return _this.getGroups(null, identity.collection, true);
        });
    };
    GraphService.prototype.publicDecrypt = function (message) {
        var decrypted = Object(__WEBPACK_IMPORTED_MODULE_11_eciesjs__["decrypt"])(this.bulletinSecretService.key.d.toHex(), Buffer.from(this.hexToByteArray(message))).toString();
        return decrypted;
    };
    GraphService.prototype.generateRids = function (identity) {
        var rid = this.generateRid(identity.username_signature, this.bulletinSecretService.identity.username_signature);
        var requested_rid = this.isGroup(identity) ? this.generateRid(identity.username_signature, identity.username_signature, identity.collection) : this.generateRid(identity.username_signature, identity.username_signature);
        var requester_rid = this.isGroup(identity) ? this.generateRid(this.bulletinSecretService.identity.username_signature, this.bulletinSecretService.identity.username_signature, identity.collection) : this.generateRid(this.bulletinSecretService.identity.username_signature, this.bulletinSecretService.identity.username_signature);
        return {
            rid: rid,
            requested_rid: requested_rid,
            requester_rid: requester_rid
        };
    };
    GraphService.prototype.isAdded = function (identity) {
        if (!identity)
            return false;
        var rids = this.generateRids(identity);
        var addedToGroups = this.isChild(identity) ?
            !!(this.groups_indexed[rids.rid] || this.groups_indexed[rids.requested_rid] || this.groups_indexed[this.generateRid(identity.username_signature, identity.username_signature, identity.parent.username_signature)])
            :
                !!(this.groups_indexed[rids.rid] || this.groups_indexed[rids.requested_rid]);
        var friend_requested_rid = this.generateRid(identity.username_signature, identity.username_signature);
        var friend_rid = this.generateRid(identity.username_signature, this.bulletinSecretService.identity.username_signature);
        var addedToFriends = !!(this.friends_indexed[friend_rid] || this.friends_indexed[friend_requested_rid]);
        return !!(addedToFriends || addedToGroups);
    };
    GraphService.prototype.isRequested = function (identity) {
        if (!identity)
            return false;
        var friend_rid = this.generateRid(identity.username_signature, this.bulletinSecretService.identity.username_signature);
        return !!this.sent_friend_requests_indexed[friend_rid];
    };
    GraphService.prototype.isGroup = function (identity) {
        if (!identity)
            return false;
        return !!identity.collection;
    };
    GraphService.prototype.isChild = function (identity) {
        if (!identity)
            return false;
        return !!identity.parent;
    };
    GraphService.prototype.toIdentity = function (identity) {
        if (!identity)
            return {};
        var iden = {
            username: identity.username,
            username_signature: identity.username_signature,
            public_key: identity.public_key
        };
        if (identity.collection) {
            iden.collection = identity.collection;
        }
        if (identity.skylink) {
            iden.skylink = identity.skylink;
        }
        return iden;
    };
    GraphService.prototype.identityToSkylink = function (identity) {
        var _this = this;
        return new Promise(function (resolve, reject) {
            var identityJson = JSON.stringify(_this.toIdentity(identity), null, 4);
            _this.ahttp.post(_this.settingsService.remoteSettings['baseUrl'] + '/sia-upload?filename=' + encodeURIComponent(identity.username_signature), { file: btoa(identityJson) })
                .subscribe(function (res) {
                var data = res.json();
                if (!data.skylink)
                    return reject(data);
                return resolve(data.skylink);
            });
        });
    };
    GraphService.prototype.inviteToSkylink = function (invite) {
        var _this = this;
        return new Promise(function (resolve, reject) {
            var identityJson = JSON.stringify(invite, null, 4);
            _this.ahttp.post(_this.settingsService.remoteSettings['baseUrl'] + '/sia-upload?filename=' + encodeURIComponent(invite.invite_signature), { file: btoa(identityJson) })
                .subscribe(function (res) {
                var data = res.json();
                if (!data.skylink)
                    return reject(data);
                return resolve(data.skylink);
            });
        });
    };
    GraphService.prototype.identityFromSkylink = function (skylink) {
        var _this = this;
        return new Promise(function (resolve, reject) {
            _this.ahttp.get('https://centeridentity.com/skynet/skylink/' + skylink)
                .subscribe(function (res) {
                try {
                    return resolve(JSON.parse(res.text()));
                }
                catch (err) {
                    return reject(err);
                }
            });
        });
    };
    GraphService.prototype.registrationStatus = function () {
        if (this.settingsService.remoteSettings.restricted &&
            !this.isAdded(this.settingsService.remoteSettings.identity) &&
            !this.isAdded(this.bulletinSecretService.identity.parent) &&
            !this.isRequested(this.settingsService.remoteSettings.identity) &&
            !this.isRequested(this.bulletinSecretService.identity.parent) &&
            this.settingsService.remoteSettings.identity.username_signature !== this.bulletinSecretService.identity.username_signature) {
            return 'error';
        }
        if (this.settingsService.remoteSettings.restricted &&
            !this.isAdded(this.settingsService.remoteSettings.identity) &&
            !this.isAdded(this.bulletinSecretService.identity.parent) &&
            (this.isRequested(this.settingsService.remoteSettings.identity) ||
                this.isRequested(this.bulletinSecretService.identity.parent)) &&
            this.settingsService.remoteSettings.identity.username_signature !== this.bulletinSecretService.identity.username_signature) {
            return 'pending';
        }
        if (this.settingsService.remoteSettings.restricted &&
            (this.isAdded(this.settingsService.remoteSettings.identity) ||
                this.isAdded(this.bulletinSecretService.identity.parent)) &&
            !this.isRequested(this.settingsService.remoteSettings.identity) &&
            !this.isRequested(this.bulletinSecretService.identity.parent) &&
            this.settingsService.remoteSettings.identity.username_signature !== this.bulletinSecretService.identity.username_signature) {
            return 'complete';
        }
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
            __WEBPACK_IMPORTED_MODULE_4__settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_5__ionic_native_badge__["a" /* Badge */],
            __WEBPACK_IMPORTED_MODULE_7_ionic_angular__["k" /* Platform */],
            __WEBPACK_IMPORTED_MODULE_6__angular_http__["b" /* Http */],
            __WEBPACK_IMPORTED_MODULE_3__transaction_service__["a" /* TransactionService */],
            __WEBPACK_IMPORTED_MODULE_9__ionic_native_geolocation__["a" /* Geolocation */],
            __WEBPACK_IMPORTED_MODULE_10__wallet_service__["a" /* WalletService */]])
    ], GraphService);
    return GraphService;
}());

//# sourceMappingURL=graph.service.js.map
/* WEBPACK VAR INJECTION */}.call(__webpack_exports__, __webpack_require__(6).Buffer))

/***/ }),

/***/ 29:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* WEBPACK VAR INJECTION */(function(Buffer) {/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return TransactionService; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__bulletinSecret_service__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__wallet_service__ = __webpack_require__(24);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__settings_service__ = __webpack_require__(22);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__angular_http__ = __webpack_require__(21);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5_eciesjs__ = __webpack_require__(342);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5_eciesjs___default = __webpack_require__.n(__WEBPACK_IMPORTED_MODULE_5_eciesjs__);
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
        this.group_username_signature = null;
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
        this.recipient_identity = null;
    }
    TransactionService.prototype.generateTransaction = function (info) {
        var _this = this;
        return new Promise(function (resolve, reject) {
            _this.key = _this.bulletinSecretService.key;
            _this.username = _this.bulletinSecretService.username;
            _this.recipient_identity = info.recipient_identity;
            _this.txnattempts = [12, 5, 4];
            _this.cbattempts = [12, 5, 4];
            _this.info = info;
            _this.group_username_signature = _this.info.group_username_signature;
            _this.unspent_transaction_override = _this.info.unspent_transaction;
            _this.blockchainurl = _this.info.blockchainurl;
            _this.callbackurl = _this.info.callbackurl;
            _this.to = _this.info.to;
            _this.value = _this.info.value;
            _this.transaction = {
                rid: _this.info.rid,
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
            if ((_this.info.relationship && _this.info.relationship.dh_private_key && _this.walletService.wallet.balance < transaction_total) /* || this.walletService.wallet.unspent_transactions.length == 0*/) {
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
                    unspent_transactions = _this.walletService.wallet.unspent_transactions;
                    unspent_transactions.sort(function (a, b) {
                        if (a.height < b.height)
                            return -1;
                        if (a.height > b.height)
                            return 1;
                        return 0;
                    });
                }
                var already_added = [];
                dance: for (var i = 0; i < unspent_transactions.length; i++) {
                    var unspent_transaction = unspent_transactions[i];
                    for (var j = 0; j < unspent_transaction.outputs.length; j++) {
                        var unspent_output = unspent_transaction.outputs[j];
                        if (unspent_output.to === _this.key.getAddress()) {
                            if (already_added.indexOf(unspent_transaction.id) === -1) {
                                already_added.push(unspent_transaction.id);
                                inputs.push({ id: unspent_transaction.id });
                                input_sum += parseFloat(unspent_output.value);
                                console.log(parseFloat(unspent_output.value));
                            }
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
            if (typeof _this.info.relationship === 'string') {
                _this.transaction.relationship = _this.info.relationship;
            }
            if (_this.info.dh_public_key && _this.info.relationship.dh_private_key) {
                // creating new relationship
                _this.transaction.relationship = _this.publicEncrypt(JSON.stringify(_this.info.relationship), _this.recipient_identity.public_key);
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
            else if (_this.info.group && !_this.info.relationship.wif) {
                // group chat
                _this.transaction.relationship = _this.shared_encrypt(_this.group_username_signature, JSON.stringify(_this.info.relationship));
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
                _this.transaction.relationship = _this.shared_encrypt(_this.group_username_signature, JSON.stringify(_this.info.relationship));
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
                _this.transaction.relationship = _this.shared_encrypt(_this.group_username_signature, JSON.stringify(_this.info.relationship));
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
                _this.transaction.relationship = _this.shared_encrypt(_this.group_username_signature, JSON.stringify(_this.info.relationship));
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
            else if (_this.info.relationship.chatText || _this.info.relationship.envelope) {
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
            else if (_this.info.relationship.wif && !_this.info.group) {
                // recovery
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
            else if (_this.info.relationship.event) {
                // calendar event
                _this.transaction.relationship = _this.encrypt();
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
            else if (_this.info.relationship.username || _this.info.relationship.wif) {
                // join or create group or contact
                if (_this.info.relationship.parent) {
                    _this.transaction.relationship = _this.shared_encrypt(_this.info.relationship.parent.username_signature, JSON.stringify(_this.info.relationship));
                }
                else {
                    _this.transaction.relationship = _this.encrypt();
                }
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
            else {
                //straight transaction
                hash = foobar.bitcoin.crypto.sha256(_this.transaction.public_key +
                    _this.transaction.time +
                    (_this.transaction.rid || '') +
                    (_this.transaction.relationship || '') +
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
                username_signature: _this.bulletinSecretService.generate_username_signature(),
                input: _this.transaction.inputs[0].id,
                id: _this.transaction.id,
                txn: _this.transaction
            })
                .subscribe(function (res) {
                try {
                    var data = res.json();
                    _this.transaction.signatures = [data.signature];
                    return resolve(data);
                }
                catch (err) {
                    return reject(err);
                }
            }, function (err) {
                reject(err);
            });
        });
    };
    TransactionService.prototype.sendTransaction = function (transactionUrlOverride) {
        var _this = this;
        if (transactionUrlOverride === void 0) { transactionUrlOverride = undefined; }
        return new Promise(function (resolve, reject) {
            var url = '';
            url = (transactionUrlOverride || _this.settingsService.remoteSettings['transactionUrl']) + '?username_signature=' + _this.bulletinSecretService.username_signature + '&to=' + _this.key.getAddress() + '&username=' + _this.username;
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
                    reject(error);
                }
            });
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
    TransactionService.prototype.hexToByteArray = function (str) {
        if (!str) {
            return new Uint8Array([]);
        }
        var a = [];
        for (var i = 0, len = str.length; i < len; i += 2) {
            a.push(parseInt(str.substr(i, 2), 16));
        }
        return new Uint8Array(a);
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
    TransactionService.prototype.publicEncrypt = function (message, public_key) {
        var data = Buffer.from(message);
        return Object(__WEBPACK_IMPORTED_MODULE_5_eciesjs__["encrypt"])(public_key, data).toString('hex');
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
    TransactionService.prototype.publicDecrypt = function (message) {
        var decrypted = Object(__WEBPACK_IMPORTED_MODULE_5_eciesjs__["decrypt"])(this.key.d.toHex(), Buffer.from(this.hexToByteArray(message))).toString();
        return decrypted;
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
/* WEBPACK VAR INJECTION */}.call(__webpack_exports__, __webpack_require__(6).Buffer))

/***/ }),

/***/ 298:
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
webpackEmptyAsyncContext.id = 298;

/***/ }),

/***/ 387:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return CalendarPage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(9);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__app_bulletinSecret_service__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_graph_service__ = __webpack_require__(26);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__mail_mailitem__ = __webpack_require__(225);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};





var CalendarPage = /** @class */ (function () {
    function CalendarPage(navCtrl, graphService, bulletinSecretService) {
        this.navCtrl = navCtrl;
        this.graphService = graphService;
        this.bulletinSecretService = bulletinSecretService;
        this.getCalendar({});
    }
    CalendarPage.prototype.addZeros = function (date) {
        return ('00' + date).substr(-2, 2);
    };
    CalendarPage.prototype.ionViewDidEnter = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            _this.loading = true;
            var rids = [_this.graphService.generateRid(_this.bulletinSecretService.identity.username_signature, _this.bulletinSecretService.identity.username_signature, 'event_meeting')];
            var group_rids = [];
            for (var i = 0; i < _this.graphService.graph.groups.length; i++) {
                var group = _this.graphService.graph.groups[i];
                group_rids.push(_this.graphService.generateRid(group.relationship.username_signature, group.relationship.username_signature, 'event_meeting'));
            }
            var file_rids = [];
            for (var i = 0; i < _this.graphService.graph.files.length; i++) {
                var file = _this.graphService.graph.files[i];
                file_rids.push(_this.graphService.generateRid(file.relationship.username_signature, file.relationship.username_signature, 'event_meeting'));
            }
            if (group_rids.length > 0) {
                rids = rids.concat(group_rids);
            }
            if (file_rids.length > 0) {
                rids = rids.concat(file_rids);
            }
            return resolve(rids);
        })
            .then(function (rids) {
            return _this.graphService.getCalendar(rids);
        })
            .then(function (data) {
            var events = {};
            _this.graphService.graph.calendar.map(function (txn) {
                var group = _this.graphService.groups_indexed[txn.requested_rid];
                var event = txn.relationship.envelope || txn.relationship.event;
                var eventDate = event.event_datetime;
                var index = eventDate.getFullYear() + _this.addZeros(eventDate.getMonth()) + _this.addZeros(eventDate.getDate());
                if (!events[index]) {
                    events[index] = [];
                }
                events[index].push({
                    group: group ? group.relationship : null,
                    sender: event.sender,
                    subject: event.subject,
                    body: event.body,
                    datetime: new Date(parseInt(txn.time) * 1000).toISOString().slice(0, 19).replace('T', ' '),
                    id: txn.id,
                    message_type: event.message_type,
                    event_datetime: event.event_datetime,
                });
            });
            _this.getCalendar(events);
            _this.loading = false;
        });
    };
    CalendarPage.prototype.itemTapped = function (event, item) {
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_4__mail_mailitem__["a" /* MailItemPage */], {
            item: item
        });
    };
    CalendarPage.prototype.getCalendar = function (events) {
        this.calendar = {
            rows: [
                {
                    days: [{}]
                }
            ]
        };
        var date = new Date();
        var month = date.getMonth();
        var year = date.getFullYear();
        var fistDay = new Date(year, month);
        var day = fistDay.getDay();
        for (var i = 0; i < 100; i++) {
            if (i < day) {
                if (this.calendar.rows.length === 0) {
                    this.calendar.rows.push({
                        days: []
                    });
                }
                this.calendar.rows[0].days.push({});
                continue;
            }
            var calDate = new Date(year, month, fistDay.getDate() + i - day);
            if (calDate.getMonth() > month)
                break;
            var index = calDate.getFullYear() + this.addZeros(calDate.getMonth()) + this.addZeros(calDate.getDate());
            if (this.calendar.rows[this.calendar.rows.length - 1].days.length >= 8) {
                this.calendar.rows.push({
                    days: [{}]
                });
            }
            this.calendar.rows[this.calendar.rows.length - 1].days.push({
                date: calDate,
                events: events[index]
            });
        }
    };
    CalendarPage = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["n" /* Component */])({
            selector: 'page-calendar',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/calendar/calendar.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n  </ion-navbar>\n</ion-header>\n<ion-content padding>\n  <ion-spinner *ngIf="loading"></ion-spinner>\n  <table width="100%" height="100%" *ngIf="calendar">\n    <tr>\n      <th width="12.5%"></th>\n      <th width="12.5%">Sunday</th>\n      <th width="12.5%">Monday</th>\n      <th width="12.5%">Tuesday</th>\n      <th width="12.5%">Wednesday</th>\n      <th width="12.5%">Thursday</th>\n      <th width="12.5%">Friday</th>\n      <th width="12.5%">Saturday</th>\n    </tr>\n    <tr *ngFor="let row of calendar.rows">\n      <td *ngFor="let day of row.days">\n        <div *ngIf="day.date">{{day.date.getDate()}}</div>\n        <div *ngIf="day.events">\n          <div *ngFor="let event of day.events">\n            <div (click)="itemTapped($event, event)">{{event.subject}}</div>\n          </div>\n        </div>\n      </td>\n    </tr>\n  </table>\n</ion-content>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/calendar/calendar.html"*/
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["i" /* NavController */],
            __WEBPACK_IMPORTED_MODULE_3__app_graph_service__["a" /* GraphService */],
            __WEBPACK_IMPORTED_MODULE_2__app_bulletinSecret_service__["a" /* BulletinSecretService */]])
    ], CalendarPage);
    return CalendarPage;
}());

//# sourceMappingURL=calendar.js.map

/***/ }),

/***/ 388:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return Settings; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(9);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__ionic_storage__ = __webpack_require__(42);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_settings_service__ = __webpack_require__(22);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_peer_service__ = __webpack_require__(221);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_bulletinSecret_service__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_firebase_service__ = __webpack_require__(224);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__list_list__ = __webpack_require__(61);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__app_graph_service__ = __webpack_require__(26);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__app_wallet_service__ = __webpack_require__(24);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_10__app_transaction_service__ = __webpack_require__(29);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_11__ionic_native_social_sharing__ = __webpack_require__(106);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_12__home_home__ = __webpack_require__(220);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_13__angular_http__ = __webpack_require__(21);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_14__ionic_native_geolocation__ = __webpack_require__(219);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_15__ionic_native_google_maps__ = __webpack_require__(389);
var __assign = (this && this.__assign) || function () {
    __assign = Object.assign || function(t) {
        for (var s, i = 1, n = arguments.length; i < n; i++) {
            s = arguments[i];
            for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p))
                t[p] = s[p];
        }
        return t;
    };
    return __assign.apply(this, arguments);
};
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
    function Settings(navCtrl, navParams, settingsService, bulletinSecretService, firebaseService, loadingCtrl, alertCtrl, storage, graphService, socialSharing, walletService, transactionService, events, toastCtrl, peerService, ahttp, geolocation, platform) {
        var _this = this;
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
        this.transactionService = transactionService;
        this.events = events;
        this.toastCtrl = toastCtrl;
        this.peerService = peerService;
        this.ahttp = ahttp;
        this.geolocation = geolocation;
        this.platform = platform;
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
        this.centerIdentityImportEnabled = false;
        this.centerIdentityExportEnabled = false;
        this.exportKeyEnabled = false;
        this.centerIdentityPrivateUsername = '';
        this.centerIdentitySaveSuccess = false;
        this.centerIdentityImportSuccess = false;
        if (typeof this.peerService.mode == 'undefined')
            this.peerService.mode = true;
        this.prefix = 'usernames-';
        this.ci = new CenterIdentity(undefined, undefined, undefined, undefined, true);
        this.refresh(null)
            .then(function () {
            return _this.peerService.go();
        }).catch(function (err) {
            console.log(err);
        });
    }
    Settings.prototype.loadMap = function (mapType) {
        var _this = this;
        /* The create() function will take the ID of your map element */
        var map = __WEBPACK_IMPORTED_MODULE_15__ionic_native_google_maps__["a" /* GoogleMaps */].create('map-' + mapType, {
            mapType: __WEBPACK_IMPORTED_MODULE_15__ionic_native_google_maps__["c" /* GoogleMapsMapTypeId */].HYBRID
        });
        map.one(__WEBPACK_IMPORTED_MODULE_15__ionic_native_google_maps__["b" /* GoogleMapsEvent */].MAP_READY).then(function (data) {
            var coordinates = new __WEBPACK_IMPORTED_MODULE_15__ionic_native_google_maps__["d" /* LatLng */](41, -87);
            map.setCameraTarget(coordinates);
            map.setCameraZoom(8);
            var service = new google.maps.places.PlacesService(map);
            service.textSearch({}, function (results, status) {
                console.log(results);
            });
        });
        map.on(__WEBPACK_IMPORTED_MODULE_15__ionic_native_google_maps__["b" /* GoogleMapsEvent */].MAP_CLICK).subscribe(function (e) {
            map.clear();
            _this.centerIdentityLocation = e[0];
            map.addMarker({
                position: e[0]
            });
        });
    };
    Settings.prototype.refresh = function (refresher) {
        var _this = this;
        this.noUsername = false;
        return this.bulletinSecretService.all()
            .then(function (keys) {
            _this.setKey(keys);
        }).then(function () {
            if (refresher)
                refresher.complete();
        });
    };
    Settings.prototype.getResults = function (keyword) {
        return ['234234', '234234'];
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
                if (a.username.toLowerCase() < b.username.toLowerCase())
                    return -1;
                if (a.username.toLowerCase() > b.username.toLowerCase())
                    return 1;
                return 0;
            });
            _this.keys = newKeys;
        })
            .then(function () {
            if (!_this.activeKey)
                return;
            if (_this.settingsService.remoteSettings.restricted) {
                _this.busy = true;
                _this.graphService.identityToSkylink(_this.bulletinSecretService.identity)
                    .then(function (skylink) {
                    _this.identitySkylink = skylink;
                    _this.busy = false;
                });
            }
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
                _this.exportKeyEnabled = true;
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
                            reject('Cancel clicked');
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
    Settings.prototype.getUsername = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
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
                            reject('Cancel clicked');
                        }
                    },
                    {
                        text: 'Save',
                        handler: function (data) {
                            resolve(data.username);
                        }
                    }
                ]
            });
            alert.present();
        });
    };
    Settings.prototype.getInvite = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            var alert = _this.alertCtrl.create({
                title: 'Set invite code',
                inputs: [
                    {
                        name: 'invite',
                        placeholder: 'Invite'
                    }
                ],
                buttons: [
                    {
                        text: 'Cancel',
                        role: 'cancel',
                        handler: function (data) {
                            console.log('Cancel clicked');
                            reject('Cancel clicked');
                        }
                    },
                    {
                        text: 'Save',
                        handler: function (data) {
                            resolve(data.invite);
                        }
                    }
                ]
            });
            alert.present();
        })
            .then(function (skylink) {
            return _this.graphService.identityFromSkylink(skylink);
        });
    };
    Settings.prototype.createWalletFromInvite = function () {
        var _this = this;
        var promise;
        var username;
        var userType;
        var userParent;
        var invite;
        this.loadingModal = this.loadingCtrl.create({
            content: 'initializing...'
        });
        this.loadingModal.present();
        promise = this.getInvite()
            .then(function (inv) {
            invite = inv;
            return _this.graphService.checkInvite(invite);
        })
            .then(function (result) {
            if (!result.status) {
                _this.bulletinSecretService.unset();
                var toast = _this.toastCtrl.create({
                    message: result.message,
                    duration: 10000
                });
                toast.present();
                throw result.message;
            }
            userType = result.type;
            userParent = result.parent;
        })
            .then(function () {
            return _this.createKey(invite.identifier);
        })
            .then(function () {
            invite = __assign({}, invite, _this.graphService.toIdentity(_this.bulletinSecretService.identity));
            return _this.graphService.checkInvite(invite);
        })
            .then(function () {
            if (userType === 'member_contact') {
                return _this.joinGroup(userParent);
            }
            else if (userType === 'organization_member') {
                return _this.joinGroup(userParent);
            }
            else if (userType === 'organization') {
                return _this.joinGroup(_this.settingsService.remoteSettings.identity);
            }
            else if (userType === 'admin') {
                return new Promise(function (resolve, reject) { return resolve(null); });
            }
        })
            .then(function () {
            return _this.selectIdentity(_this.bulletinSecretService.keyname.substr(_this.prefix.length), false);
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
            _this.loadingModal.dismiss();
        })
            .then(function () {
            var toast = _this.toastCtrl.create({
                message: 'Identity created',
                duration: 2000
            });
            toast.present();
        })
            .catch(function () {
            _this.events.publish('pages');
            _this.loadingModal.dismiss();
        });
    };
    Settings.prototype.createWallet = function () {
        var _this = this;
        var promise;
        var username;
        var userType;
        var userParent;
        this.loadingModal = this.loadingCtrl.create({
            content: 'initializing...'
        });
        this.loadingModal.present();
        promise = this.getUsername()
            .then(function (username) {
            return _this.createKey(username);
        })
            .then(function () {
            _this.loadingModal.dismiss();
        })
            .catch(function () {
            _this.loadingModal.dismiss();
        });
        promise
            .then(function () {
            var toast = _this.toastCtrl.create({
                message: 'Identity created',
                duration: 2000
            });
            toast.present();
        });
    };
    Settings.prototype.createKey = function (username) {
        var _this = this;
        return new Promise(function (resolve, reject) {
            _this.bulletinSecretService.create(username)
                .then(function () {
                return resolve(username);
            });
        })
            .then(function (key) {
            return _this.set(key);
        })
            .then(function () {
            return _this.save();
        });
    };
    Settings.prototype.selectIdentity = function (key, showModal) {
        var _this = this;
        if (showModal === void 0) { showModal = true; }
        this.graphService.resetGraph();
        if (showModal) {
            this.loadingModal = this.loadingCtrl.create({
                content: 'initializing...'
            });
            this.loadingModal.present();
        }
        if (this.settingsService.remoteSettings.restricted) {
            return this.set(key)
                .then(function () {
                return _this.graphService.refreshFriendsAndGroups();
            })
                .then(function () {
                return _this.graphService.getUserType(_this.bulletinSecretService.identity.username);
            })
                .then(function (result) {
                if (result.status) {
                    var userType = result.type;
                    _this.bulletinSecretService.identity.type = result.type;
                    _this.bulletinSecretService.identity.parent = result.parent;
                    if (userType === 'member_contact') {
                        if (!_this.graphService.isAdded(_this.bulletinSecretService.identity.parent))
                            return _this.joinGroup(_this.bulletinSecretService.identity.parent);
                    }
                    else if (userType === 'organization_member') {
                        if (!_this.graphService.isAdded(_this.bulletinSecretService.identity.parent))
                            return _this.joinGroup(_this.bulletinSecretService.identity.parent);
                    }
                    else if (userType === 'organization') {
                        if (!_this.graphService.isAdded(_this.bulletinSecretService.identity.parent))
                            return _this.joinGroup(_this.bulletinSecretService.identity.parent);
                    }
                    else if (userType === 'admin') {
                        return new Promise(function (resolve, reject) { return resolve(null); });
                    }
                }
                else {
                    _this.bulletinSecretService.unset();
                    var toast = _this.toastCtrl.create({
                        message: result.message,
                        duration: 10000
                    });
                    toast.present();
                    throw result.message;
                }
            })
                .then(function () {
                if (showModal) {
                    _this.loadingModal.dismiss();
                }
                _this.settingsService.menu = 'home';
                _this.navCtrl.setRoot(__WEBPACK_IMPORTED_MODULE_12__home_home__["a" /* HomePage */], { pageTitle: { title: 'Home', label: 'Home', component: __WEBPACK_IMPORTED_MODULE_12__home_home__["a" /* HomePage */], count: false, color: '' } });
            })
                .catch(function (err) {
                console.log(err);
                if (showModal) {
                    _this.loadingModal.dismiss();
                }
            });
        }
        else {
            return this.set(key)
                .then(function () {
                return _this.graphService.refreshFriendsAndGroups();
            })
                .then(function () {
                if (showModal) {
                    _this.loadingModal.dismiss();
                }
                _this.settingsService.menu = 'home';
                _this.navCtrl.setRoot(__WEBPACK_IMPORTED_MODULE_12__home_home__["a" /* HomePage */], { pageTitle: { title: 'Home', label: 'Home', component: __WEBPACK_IMPORTED_MODULE_12__home_home__["a" /* HomePage */], count: false, color: '' } });
            })
                .catch(function (err) {
                console.log(err);
                if (showModal) {
                    _this.loadingModal.dismiss();
                }
            });
        }
    };
    Settings.prototype.joinGroup = function (iden) {
        var _this = this;
        var identity = JSON.parse(JSON.stringify(iden)); //deep copy
        identity.collection = 'group';
        return this.graphService.addGroup(identity)
            .then(function () {
            return _this.graphService.addFriend(iden);
        });
    };
    Settings.prototype.unlockWallet = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            var options = new __WEBPACK_IMPORTED_MODULE_13__angular_http__["d" /* RequestOptions */]({ withCredentials: true });
            _this.ahttp.post(_this.settingsService.remoteSettings['baseUrl'] + '/unlock?origin=' + encodeURIComponent(window.location.origin), { key_or_wif: _this.activeKey }, options)
                .subscribe(function (res) {
                _this.settingsService.tokens[_this.bulletinSecretService.keyname] = res.json()['token'];
                if (!_this.settingsService.tokens[_this.bulletinSecretService.keyname])
                    return resolve(res);
                var toast = _this.toastCtrl.create({
                    message: 'Wallet unlocked!',
                    duration: 2000
                });
                toast.present();
                resolve(res);
            }, function (err) {
                return reject('cannot unlock wallet');
            });
        });
    };
    Settings.prototype.set = function (key) {
        this.storage.set('last-keyname', this.prefix + key);
        return this.doSet(this.prefix + key)
            .catch(function () {
            console.log('can not set identity');
        });
    };
    Settings.prototype.doSet = function (keyname) {
        var _this = this;
        return new Promise(function (resolve, reject) {
            _this.bulletinSecretService.set(keyname)
                .then(function () {
                _this.serverDown = false;
                if (!document.URL.startsWith('http') || document.URL.startsWith('http://localhost:8080')) {
                    _this.firebaseService.initFirebase();
                }
                return resolve();
            }).catch(function (error) {
                _this.serverDown = true;
                return reject(error);
            });
        });
    };
    Settings.prototype.save = function () {
        this.graphService.resetGraph();
        return this.set(this.bulletinSecretService.keyname.substr(this.prefix.length));
    };
    Settings.prototype.showChat = function () {
        var item = { pageTitle: { title: "Chat" } };
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_7__list_list__["a" /* ListPage */], item);
    };
    Settings.prototype.showFriendRequests = function () {
        var item = { pageTitle: { title: "Friend Requests" } };
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_7__list_list__["a" /* ListPage */], item);
    };
    Settings.prototype.enableCenterIdentityImport = function () {
        this.centerIdentityImportEnabled = true;
        this.loadMap('import');
    };
    Settings.prototype.enableCenterIdentityExport = function () {
        this.centerIdentityExportEnabled = true;
        this.loadMap('export');
    };
    Settings.prototype.getKeyUsingCenterIdentity = function () {
        var _this = this;
        this.CIBusy = true;
        return this.ci.get(this.centerIdentityPrivateUsername, this.centerIdentityLocation.lat.toFixed(3), this.centerIdentityLocation.lng.toFixed(3))
            .then(function (identity) {
            _this.CIBusy = false;
            _this.importedKey = identity.wif;
            return _this.importKey();
        });
    };
    Settings.prototype.saveKeyUsingCenterIdentity = function () {
        var _this = this;
        var fullIdentity = {
            key: this.bulletinSecretService.key,
            wif: this.bulletinSecretService.key.toWIF(),
            public_key: this.identity.public_key,
            username: this.centerIdentityPrivateUsername,
        };
        return this.walletService.get(1)
            .then(function (txns) {
            return _this.ci.set(fullIdentity, _this.centerIdentityLocation.lat, _this.centerIdentityLocation.lng);
        })
            .then(function (txns) {
            var friendTxn = txns[0];
            _this.transactionService.generateTransaction(friendTxn);
            _this.transactionService.sendTransaction('https://centeridentity.com/transaction');
            var buryTxn = txns[1];
            buryTxn.to = '1EWkrpUezWMpByE6nys6VXubjFLorgbZuP';
            buryTxn.value = 1;
            _this.transactionService.generateTransaction(buryTxn);
            _this.transactionService.sendTransaction('https://centeridentity.com/transaction');
            _this.centerIdentitySaveSuccess = true;
        });
    };
    Settings = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["n" /* Component */])({
            selector: 'page-settings',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/settings/settings.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n  </ion-navbar>\n</ion-header>\n\n<ion-content padding>\n  <ion-refresher (ionRefresh)="refresh($event)">\n    <ion-refresher-content></ion-refresher-content>\n  </ion-refresher>\n  <h1>Sign-in</h1>\n  <h3>Create an identity</h3>\n  <button ion-button secondary (click)="createWallet()" *ngIf="!settingsService.remoteSettings.restricted">Create identity</button>\n  <button ion-button secondary (click)="createWalletFromInvite()" *ngIf="settingsService.remoteSettings.restricted">Create identity from Code</button>\n  <h3 *ngIf="keys && keys.length > 0">Select an identity</h3>\n  <ion-list>\n    <button *ngFor="let key of keys" ion-item (click)="selectIdentity(key.username)" [color]="key.active ? \'primary\' : \'light\'">\n      <ion-icon name="person" item-start [color]="\'dark\'"></ion-icon>\n      {{key.username}}\n    </button>\n  </ion-list>\n  <ion-list *ngIf="bulletinSecretService.keyname && !centerIdentityExportEnabled">\n    <ion-item>\n      Make the active identity available anywhere using the YadaCoin blockchain and maps provided by Center Identity\n      <button ion-button secondary (click)="enableCenterIdentityExport()">Enable</button>\n    </ion-item>\n  </ion-list>\n  <ion-list *ngIf="bulletinSecretService.keyname && centerIdentityExportEnabled">\n    <ion-item style="background: linear-gradient(90deg, rgba(255,255,255,1) 0%, #191919 75%); color: black;"><img src="assets/center-identity-logo1024x500.png" height="65" style="vertical-align:middle"></ion-item>\n    <ion-item>\n      <ion-input type="text" placeholder="Public username" [(ngModel)]="identity.username" disabled></ion-input>\n    </ion-item>\n    <ion-item>\n      Pick a private username that nobody knows except for you (must be very memorable)\n    </ion-item>\n    <ion-item>\n      Pick a private username that nobody knows except for you (must be very memorable)\n      <ion-input type="text" placeholder="Private username" [(ngModel)]="centerIdentityPrivateUsername"></ion-input>\n    </ion-item>\n    <ion-item>\n      Pick a private location that nobody knows except for you (must be very memorable)\n      <div id="map-export" style="width:500px;height:500px;"></div>\n    </ion-item>\n    <ion-item *ngIf="!centerIdentitySaveSuccess">\n      <button ion-button secondary (click)="saveKeyUsingCenterIdentity()">Save to blockchain</button>\n    </ion-item>\n    <ion-item *ngIf="centerIdentitySaveSuccess">\n      <button ion-button primary (click)="saveKeyUsingCenterIdentity()" disabled>Success!</button>\n    </ion-item>\n  </ion-list>\n  <ion-list *ngIf="bulletinSecretService.keyname">\n    <hr/>\n    <h4>Export wif (private, do not share)</h4>\n    <ion-item *ngIf="!exportKeyEnabled">\n      <button ion-button secondary (click)="exportKey()">Export active identity</button>\n    </ion-item>\n    <ion-item *ngIf="exportKeyEnabled">\n      <ion-input type="text" [(ngModel)]="activeKey"></ion-input>\n    </ion-item>\n    <h4>Public identity (share this with your friends) <ion-spinner *ngIf="busy"></ion-spinner></h4>\n    <ion-item *ngIf="settingsService.remoteSettings.restricted">\n      <ion-textarea type="text" [(ngModel)]="identitySkylink" autoGrow="true" rows=1></ion-textarea>\n    </ion-item>\n    <ion-item *ngIf="!settingsService.remoteSettings.restricted">\n      <ion-textarea type="text" [value]="bulletinSecretService.identityJson()" autoGrow="true" rows="5"></ion-textarea>\n    </ion-item>\n  </ion-list>\n  <h4>Import using location</h4>\n  <ion-item *ngIf="!centerIdentityImportEnabled">\n    <button ion-button secondary (click)="enableCenterIdentityImport()">Choose location</button>\n  </ion-item>\n  <ion-list *ngIf="centerIdentityImportEnabled">\n    <ion-item>\n      Enter your private username\n      <ion-input type="text" placeholder="Private username" [(ngModel)]="centerIdentityPrivateUsername"></ion-input>\n    </ion-item>\n    <ion-item>\n      Select your private location\n      <div id="map-import" style="width:500px;height:500px;"></div>\n    </ion-item>\n    <ion-item *ngIf="!centerIdentityImportSuccess">\n      <button ion-button secondary (click)="getKeyUsingCenterIdentity()">Get from blockchain <ion-spinner *ngIf="CIBusy"></ion-spinner></button>\n    </ion-item>\n    <ion-item *ngIf="centerIdentityImportSuccess">\n      <button ion-button primary (click)="getKeyUsingCenterIdentity()" disabled>Success!</button>\n    </ion-item>\n  </ion-list>\n  <h4>Import WIF</h4>\n  <ion-item>\n    <ion-label floating>WIF</ion-label>\n    <ion-input type="text" [(ngModel)]="importedKey"></ion-input>\n  </ion-item>\n  <ion-item>\n    <button ion-button secondary (click)="importKey()">Import identity</button>\n  </ion-item>\n</ion-content>\n'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/settings/settings.html"*/
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
            __WEBPACK_IMPORTED_MODULE_11__ionic_native_social_sharing__["a" /* SocialSharing */],
            __WEBPACK_IMPORTED_MODULE_9__app_wallet_service__["a" /* WalletService */],
            __WEBPACK_IMPORTED_MODULE_10__app_transaction_service__["a" /* TransactionService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["b" /* Events */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["l" /* ToastController */],
            __WEBPACK_IMPORTED_MODULE_4__app_peer_service__["a" /* PeerService */],
            __WEBPACK_IMPORTED_MODULE_13__angular_http__["b" /* Http */],
            __WEBPACK_IMPORTED_MODULE_14__ionic_native_geolocation__["a" /* Geolocation */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["k" /* Platform */]])
    ], Settings);
    return Settings;
}());

//# sourceMappingURL=settings.js.map

/***/ }),

/***/ 390:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return StreamPage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(9);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__ionic_storage__ = __webpack_require__(42);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_graph_service__ = __webpack_require__(26);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_bulletinSecret_service__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_wallet_service__ = __webpack_require__(24);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_transaction_service__ = __webpack_require__(29);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__app_settings_service__ = __webpack_require__(22);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__angular_http__ = __webpack_require__(21);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__angular_platform_browser__ = __webpack_require__(55);
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
            _this.graphService.getGroupMessages(group['relationship']['username_signature'], null, group.rid)
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
            selector: 'page-stream',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/stream/stream.html"*/'<ion-header>\n    <ion-navbar>\n        <button ion-button menuToggle color="{{color}}">\n            <ion-icon name="menu"></ion-icon>\n        </button>\n        <ion-title>{{label}}</ion-title>\n    </ion-navbar>\n</ion-header>\n<ion-content>\n    <ion-list *ngIf="!error">\n        <button ion-item *ngFor="let group of groups" (click)="selectGroup(group.requested_rid || group.rid)">{{group.relationship.identity.username}}</button>\n    </ion-list>\n    <iframe [src]="sanitize(streamUrl)" width="100%" height="100%" border="0" *ngIf="streamUrl && !error" id="iframe"></iframe>\n    <ion-item *ngIf="error">You must download the <a href="https://github.com/pdxwebdev/yadacoin/releases/latest" target="_blank">full node</a> to stream content from the blockchain.</ion-item>\n</ion-content>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/stream/stream.html"*/,
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

/***/ 391:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return SendReceive; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(9);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__app_wallet_service__ = __webpack_require__(24);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_transaction_service__ = __webpack_require__(29);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_bulletinSecret_service__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__ionic_native_qr_scanner__ = __webpack_require__(392);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_settings_service__ = __webpack_require__(22);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__ionic_native_social_sharing__ = __webpack_require__(106);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__list_list__ = __webpack_require__(61);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__angular_http__ = __webpack_require__(21);
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
        this.createdCode = bulletinSecretService.key.getAddress();
        this.refresh();
        this.sentPage = 1;
        this.receivedPage = 1;
        this.sentPendingPage = 1;
        this.receivedPendingPage = 1;
        this.past_sent_transactions = [];
        this.past_sent_pending_transactions = [];
        this.past_received_transactions = [];
        this.past_received_pending_transactions = [];
        this.sentPendingLoading = false;
        this.receivedPendingLoading = false;
        this.sentLoading = false;
        this.receivedLoading = false;
        this.past_sent_page_cache = {};
        this.past_sent_pending_page_cache = {};
        this.past_received_page_cache = {};
        this.past_received_pending_page_cache = {};
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
                    _this.value = '0';
                    _this.address = '';
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
        })
            .then(function () {
            _this.getSentHistory();
        })
            .then(function () {
            _this.getSentPendingHistory();
        })
            .then(function () {
            _this.getReceivedHistory();
        })
            .then(function () {
            _this.getReceivedPendingHistory();
        }).catch(function (err) {
            console.log(err);
        });
    };
    SendReceive.prototype.convertDateTime = function (timestamp) {
        var a = new Date(timestamp * 1000);
        var months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        var year = a.getFullYear();
        var month = months[a.getMonth()];
        var date = a.getDate();
        var hour = '0' + a.getHours();
        var min = '0' + a.getMinutes();
        var time = date + '-' + month + '-' + year + ' ' + hour.substr(-2) + ':' + min.substr(-2);
        return time;
    };
    SendReceive.prototype.getSentPendingHistory = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            _this.sentPendingLoading = true;
            var options = new __WEBPACK_IMPORTED_MODULE_9__angular_http__["d" /* RequestOptions */]({ withCredentials: true });
            _this.ahttp.get(_this.settingsService.remoteSettings['baseUrl'] + '/get-past-pending-sent-txns?page=' + _this.sentPendingPage + '&public_key=' + _this.bulletinSecretService.key.getPublicKeyBuffer().toString('hex') + '&origin=' + encodeURIComponent(window.location.origin), options)
                .subscribe(function (res) {
                _this.sentPendingLoading = false;
                _this.past_sent_pending_transactions = res.json()['past_pending_transactions'].sort(_this.sortFunc);
                _this.getSentOutputValue(_this.past_sent_pending_transactions);
                _this.past_sent_pending_page_cache[_this.sentPendingPage] = _this.past_sent_pending_transactions;
                resolve(res);
            }, function (err) {
                return reject('cannot unlock wallet');
            });
        });
    };
    SendReceive.prototype.getSentHistory = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            _this.sentLoading = true;
            var options = new __WEBPACK_IMPORTED_MODULE_9__angular_http__["d" /* RequestOptions */]({ withCredentials: true });
            _this.ahttp.get(_this.settingsService.remoteSettings['baseUrl'] + '/get-past-sent-txns?page=' + _this.sentPage + '&public_key=' + _this.bulletinSecretService.key.getPublicKeyBuffer().toString('hex') + '&origin=' + encodeURIComponent(window.location.origin), options)
                .subscribe(function (res) {
                _this.sentLoading = false;
                _this.past_sent_transactions = res.json()['past_transactions'].sort(_this.sortFunc);
                _this.getSentOutputValue(_this.past_sent_transactions);
                _this.past_sent_page_cache[_this.sentPage] = _this.past_sent_transactions;
                resolve(res);
            }, function (err) {
                return reject('cannot unlock wallet');
            });
        });
    };
    SendReceive.prototype.getReceivedPendingHistory = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            _this.receivedPendingLoading = true;
            var options = new __WEBPACK_IMPORTED_MODULE_9__angular_http__["d" /* RequestOptions */]({ withCredentials: true });
            _this.ahttp.get(_this.settingsService.remoteSettings['baseUrl'] + '/get-past-pending-received-txns?page=' + _this.receivedPendingPage + '&public_key=' + _this.bulletinSecretService.key.getPublicKeyBuffer().toString('hex') + '&origin=' + encodeURIComponent(window.location.origin), options)
                .subscribe(function (res) {
                _this.receivedPendingLoading = false;
                _this.past_received_pending_transactions = res.json()['past_pending_transactions'].sort(_this.sortFunc);
                _this.getReceivedOutputValue(_this.past_received_pending_transactions);
                _this.past_received_pending_page_cache[_this.receivedPendingPage] = _this.past_received_pending_transactions;
                resolve(res);
            }, function (err) {
                return reject('cannot unlock wallet');
            });
        });
    };
    SendReceive.prototype.getReceivedHistory = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            _this.receivedLoading = true;
            var options = new __WEBPACK_IMPORTED_MODULE_9__angular_http__["d" /* RequestOptions */]({ withCredentials: true });
            _this.ahttp.get(_this.settingsService.remoteSettings['baseUrl'] + '/get-past-received-txns?page=' + _this.receivedPage + '&public_key=' + _this.bulletinSecretService.key.getPublicKeyBuffer().toString('hex') + '&origin=' + encodeURIComponent(window.location.origin), options)
                .subscribe(function (res) {
                _this.receivedLoading = false;
                _this.past_received_transactions = res.json()['past_transactions'].sort(_this.sortFunc);
                _this.getReceivedOutputValue(_this.past_received_transactions);
                _this.past_received_page_cache[_this.receivedPage] = _this.past_received_transactions;
                resolve(res);
            }, function (err) {
                return reject('cannot unlock wallet');
            });
        });
    };
    SendReceive.prototype.getReceivedOutputValue = function (array) {
        for (var i = 0; i < array.length; i++) {
            var txn = array[i];
            if (!array[i]['value']) {
                array[i]['value'] = 0;
            }
            for (var j = 0; j < txn['outputs'].length; j++) {
                var output = txn['outputs'][j];
                if (this.bulletinSecretService.key.getAddress() === output.to) {
                    array[i]['value'] += parseFloat(output.value);
                }
            }
            array[i]['value'] = array[i]['value'].toFixed(8);
        }
    };
    SendReceive.prototype.getSentOutputValue = function (array) {
        for (var i = 0; i < array.length; i++) {
            var txn = array[i];
            if (!array[i]['value']) {
                array[i]['value'] = 0;
            }
            for (var j = 0; j < txn['outputs'].length; j++) {
                var output = txn['outputs'][j];
                if (this.bulletinSecretService.key.getAddress() !== output.to) {
                    array[i]['value'] += parseFloat(output.value);
                }
            }
            array[i]['value'] = array[i]['value'].toFixed(8);
        }
    };
    SendReceive.prototype.sortFunc = function (a, b) {
        if (parseInt(a.time) < parseInt(b.time))
            return 1;
        if (parseInt(a.time) > parseInt(b.time))
            return -1;
        return 0;
    };
    SendReceive.prototype.prevReceivedPage = function () {
        this.receivedPage--;
        var result = this.past_received_page_cache[this.receivedPage] || [];
        if (result.length > 0) {
            this.past_received_transactions = result;
            return;
        }
        return this.getReceivedHistory();
    };
    SendReceive.prototype.nextReceivedPage = function () {
        this.receivedPage++;
        var result = this.past_received_page_cache[this.receivedPage] || [];
        if (result.length > 0) {
            this.past_received_transactions = result;
            return;
        }
        return this.getReceivedHistory();
    };
    SendReceive.prototype.prevReceivedPendingPage = function () {
        this.receivedPendingPage--;
        var result = this.past_received_pending_page_cache[this.receivedPendingPage] || [];
        if (result.length > 0) {
            this.past_received_pending_transactions = result;
            return;
        }
        return this.getReceivedPendingHistory();
    };
    SendReceive.prototype.nextReceivedPendingPage = function () {
        this.receivedPendingPage++;
        var result = this.past_received_pending_transactions = this.past_received_pending_page_cache[this.receivedPendingPage] || [];
        if (result.length > 0) {
            this.past_sent_transactions = result;
            return;
        }
        return this.getReceivedPendingHistory();
    };
    SendReceive.prototype.prevSentPage = function () {
        this.sentPage--;
        var result = this.past_sent_transactions = this.past_sent_page_cache[this.sentPage] || [];
        if (result.length > 0) {
            this.past_sent_transactions = result;
            return;
        }
        return this.getSentHistory();
    };
    SendReceive.prototype.nextSentPage = function () {
        this.sentPage++;
        var result = this.past_sent_page_cache[this.sentPage] || [];
        if (result.length > 0) {
            this.past_sent_transactions = result;
            return;
        }
        return this.getSentHistory();
    };
    SendReceive.prototype.prevSentPendingPage = function () {
        this.sentPendingPage--;
        var result = this.past_sent_pending_transactions = this.past_sent_pending_page_cache[this.sentPendingPage] || [];
        if (result.length > 0) {
            this.past_sent_pending_transactions = result;
            return;
        }
        return this.getSentPendingHistory();
    };
    SendReceive.prototype.nextSentPendingPage = function () {
        this.sentPendingPage++;
        var result = this.past_sent_pending_page_cache[this.sentPendingPage] || [];
        if (result.length > 0) {
            this.past_sent_pending_transactions = result;
            return;
        }
        return this.getSentPendingHistory();
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
            selector: 'page-sendreceive',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/sendreceive/sendreceive.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n  </ion-navbar>\n</ion-header>\n<ion-content padding>\n  <ion-refresher (ionRefresh)="refresh($event)">\n    <ion-refresher-content></ion-refresher-content>\n  </ion-refresher>\n  <h4>Balance</h4>\n  <ion-item>\n    {{walletService.wallet.balance}} YADA\n  </ion-item>\n  <h4>Send YadaCoins</h4>\n  <button *ngIf="isDevice" ion-button color="secondary" (click)="scan()" full>Scan Address</button>\n  <ion-item>\n    <ion-label color="primary" stacked>Address</ion-label>\n    <ion-input type="text" placeholder="Recipient address..." [(ngModel)]="address">\n    </ion-input>\n  </ion-item>\n  <ion-item>\n    <ion-label color="primary" fixed>Amount</ion-label>\n    <ion-input type="number" placeholder="Amount..." [(ngModel)]="value">\n    </ion-input>\n  </ion-item>\n  <button ion-button secondary (click)="submit()">Send</button>\n  <h4>Receive YadaCoins</h4>\n  <ion-item>\n    <ion-label color="primary" stacked>Your Address:</ion-label>\n    <ion-input type="text" [(ngModel)]="createdCode"></ion-input>\n  </ion-item>\n  <button *ngIf="isDevice" ion-button outline item-end (click)="shareAddress()">share address&nbsp;<ion-icon name="share"></ion-icon></button>\n  <ion-card>\n    <ion-card-content>\n      <ngx-qrcode [qrc-value]="createdCode"></ngx-qrcode>\n    </ion-card-content>\n  </ion-card>\n  <h4>Pending Transactions</h4>\n  <strong>Received</strong><br>\n  <button ion-button small (click)="prevReceivedPendingPage()" [disabled]="receivedPendingPage <= 1">< Prev</button> <button ion-button small (click)="nextReceivedPendingPage()" [disabled]="past_received_pending_transactions.length === 0 || past_received_pending_transactions.length < 10">Next ></button>\n  <p *ngIf="past_received_pending_transactions.length === 0">No more results</p><span *ngIf="receivedPendingLoading"> (loading...)</span>\n  <ion-list>\n    <ion-item *ngFor="let txn of past_received_pending_transactions">\n      <ion-label>{{convertDateTime(txn.time)}}</ion-label>\n      <ion-label><a href="https://yadacoin.io/explorer?term={{txn.id}}" target="_blank">{{txn.id}}</a></ion-label>\n      <ion-label>{{txn.value}}</ion-label>\n    </ion-item>\n  </ion-list>\n  <strong>Sent</strong><br>\n  <button ion-button small (click)="prevSentPendingPage()" [disabled]="sentPendingPage <= 1">< Prev</button> <button ion-button small (click)="nextSentPendingPage()" [disabled]="past_sent_pending_transactions.length === 0 || past_sent_pending_transactions.length < 10">Next ></button>\n  <p *ngIf="past_sent_pending_transactions.length === 0">No more results</p><span *ngIf="sentPendingLoading"> (loading...)</span>\n  <ion-list>\n    <ion-item *ngFor="let txn of past_sent_pending_transactions">\n      <ion-label>{{convertDateTime(txn.time)}}</ion-label>\n      <ion-label><a href="https://yadacoin.io/explorer?term={{txn.id}}" target="_blank">{{txn.id}}</a></ion-label>\n      <ion-label>{{txn.value}}</ion-label>\n    </ion-item>\n  </ion-list>\n  <h4>Transaction history</h4>\n  <strong>Received</strong><br>\n  <button ion-button small (click)="prevReceivedPage()" [disabled]="receivedPage <= 1">< Prev</button> <button ion-button small (click)="nextReceivedPage()" [disabled]="past_received_transactions.length === 0 || past_received_transactions.length < 10">Next ></button>\n  <p *ngIf="past_received_transactions.length === 0">No more results</p><span *ngIf="receivedLoading"> (loading...)</span>\n  <ion-list>\n    <ion-item *ngFor="let txn of past_received_transactions">\n      <ion-label>{{convertDateTime(txn.time)}}</ion-label>\n      <ion-label><a href="https://yadacoin.io/explorer?term={{txn.id}}" target="_blank">{{txn.id}}</a></ion-label>\n      <ion-label>{{txn.value}}</ion-label>\n    </ion-item>\n  </ion-list>\n  <strong>Sent</strong><br>\n  <button ion-button small (click)="prevSentPage()" [disabled]="sentPage <= 1">< Prev</button> <button ion-button small (click)="nextSentPage()" [disabled]="past_sent_transactions.length === 0 || past_sent_transactions.length < 10">Next ></button>\n  <p *ngIf="past_sent_transactions.length === 0">No more results</p><span *ngIf="sentLoading"> (loading...)</span>\n  <ion-list>\n    <ion-item *ngFor="let txn of past_sent_transactions">\n      <ion-label>{{convertDateTime(txn.time)}}</ion-label>\n      <ion-label><a href="https://yadacoin.io/explorer?term={{txn.id}}" target="_blank">{{txn.id}}</a></ion-label>\n      <ion-label>{{txn.value}}</ion-label>\n    </ion-item>\n  </ion-list>\n</ion-content>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/sendreceive/sendreceive.html"*/
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

/***/ 393:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return MailPage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(9);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__app_bulletinSecret_service__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_graph_service__ = __webpack_require__(26);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__compose__ = __webpack_require__(134);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__mailitem__ = __webpack_require__(225);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};






var MailPage = /** @class */ (function () {
    function MailPage(navCtrl, navParams, graphService, bulletinSecretService) {
        var _this = this;
        this.navCtrl = navCtrl;
        this.navParams = navParams;
        this.graphService = graphService;
        this.bulletinSecretService = bulletinSecretService;
        this.items = [];
        this.loading = false;
        this.loading = true;
        var rids = [this.graphService.generateRid(this.bulletinSecretService.identity.username_signature, this.bulletinSecretService.identity.username_signature, 'mail'),
            this.graphService.generateRid(this.bulletinSecretService.identity.username_signature, this.bulletinSecretService.identity.username_signature, 'contract'),
            this.graphService.generateRid(this.bulletinSecretService.identity.username_signature, this.bulletinSecretService.identity.username_signature, 'contract_signed'),
            this.graphService.generateRid(this.bulletinSecretService.identity.username_signature, this.bulletinSecretService.identity.username_signature, 'event_meeting')];
        var group_rids = [];
        for (var i = 0; i < this.graphService.graph.groups.length; i++) {
            var group = this.graphService.graph.groups[i];
            group_rids.push(this.graphService.generateRid(group.relationship.username_signature, group.relationship.username_signature, 'group_mail'));
        }
        var file_rids = [];
        for (var i = 0; i < this.graphService.graph.files.length; i++) {
            var group = this.graphService.graph.files[i];
            file_rids.push(this.graphService.generateRid(group.relationship.username_signature, group.relationship.username_signature, 'group_mail'));
        }
        if (group_rids.length > 0) {
            rids = rids.concat(group_rids);
        }
        if (file_rids.length > 0) {
            rids = rids.concat(file_rids);
        }
        this.graphService.getMail(rids)
            .then(function () {
            _this.items = _this.graphService.graph.mail.filter(function (item) {
                if (_this.navParams.data.pageTitle.label === 'Sent' && item.public_key === _this.bulletinSecretService.identity.public_key)
                    return true;
                if (_this.navParams.data.pageTitle.label === 'Inbox' && item.public_key !== _this.bulletinSecretService.identity.public_key)
                    return true;
            }).map(function (item) {
                var group = _this.graphService.groups_indexed[item.requested_rid];
                var indexedItem = _this.graphService.groups_indexed[item.requested_rid] || _this.graphService.friends_indexed[item.rid];
                var identity = indexedItem.relationship.identity || indexedItem.relationship;
                var sender;
                if (item.relationship.envelope.sender) {
                    sender = item.relationship.envelope.sender;
                }
                else if (item.public_key === _this.bulletinSecretService.identity.public_key && _this.navParams.data.pageTitle.label === 'Inbox') {
                    sender = _this.bulletinSecretService.identity;
                }
                else {
                    sender = {
                        username: identity.username,
                        username_signature: identity.username_signature,
                        public_key: identity.public_key
                    };
                }
                return {
                    sender: sender,
                    group: group ? group.relationship : null,
                    subject: item.relationship.envelope.subject,
                    body: item.relationship.envelope.body,
                    datetime: new Date(parseInt(item.time) * 1000).toISOString().slice(0, 19).replace('T', ' '),
                    id: item.id,
                    thread: item.relationship.thread,
                    message_type: item.relationship.envelope.message_type,
                    event_datetime: item.relationship.envelope.event_datetime,
                    skylink: item.relationship.envelope.skylink,
                    filename: item.relationship.envelope.filename
                };
            });
            _this.loading = false;
        });
    }
    MailPage.prototype.itemTapped = function (event, item) {
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_5__mailitem__["a" /* MailItemPage */], {
            item: item
        });
    };
    MailPage.prototype.composeMail = function () {
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_4__compose__["a" /* ComposePage */]);
    };
    MailPage = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["n" /* Component */])({
            selector: 'mail-profile',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/mail/mail.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n  </ion-navbar>\n</ion-header>\n<ion-content padding>\n  <ion-refresher (ionRefresh)="refresh($event)">\n    <ion-refresher-content></ion-refresher-content>\n  </ion-refresher>\n  <ion-spinner *ngIf="loading"></ion-spinner>\n  <button ion-button secondary (click)="composeMail()">Compose</button>\n  <ion-card *ngIf="items && items.length == 0">\n      <ion-card-content>\n        <ion-card-title style="text-overflow:ellipsis;" text-wrap>\n          No items to display.\n      </ion-card-title>\n    </ion-card-content>\n  </ion-card>\n  <ion-list>\n    <button ion-item *ngFor="let item of items" (click)="itemTapped($event, item)">\n      <ion-item>\n        <div title="Verified" class="sender">\n          <span>{{item.sender.username}} <ion-icon name="checkmark-circle" class="success"></ion-icon></span>\n          <span *ngIf="item.group">{{item.group.username}} <ion-icon name="checkmark-circle" class="success"></ion-icon></span>\n        </div>\n        <div class="subject">{{item.subject}}</div>\n        <div class="datetime">{{item.datetime}}</div>\n        <div class="body">{{item.body}}</div>\n      </ion-item>\n    </button>\n  </ion-list>\n</ion-content>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/mail/mail.html"*/
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["i" /* NavController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["j" /* NavParams */],
            __WEBPACK_IMPORTED_MODULE_3__app_graph_service__["a" /* GraphService */],
            __WEBPACK_IMPORTED_MODULE_2__app_bulletinSecret_service__["a" /* BulletinSecretService */]])
    ], MailPage);
    return MailPage;
}());

//# sourceMappingURL=mail.js.map

/***/ }),

/***/ 407:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
Object.defineProperty(__webpack_exports__, "__esModule", { value: true });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_platform_browser_dynamic__ = __webpack_require__(408);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__app_module__ = __webpack_require__(518);


Object(__WEBPACK_IMPORTED_MODULE_0__angular_platform_browser_dynamic__["a" /* platformBrowserDynamic */])().bootstrapModule(__WEBPACK_IMPORTED_MODULE_1__app_module__["a" /* AppModule */]);
//# sourceMappingURL=main.js.map

/***/ }),

/***/ 518:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return AppModule; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_platform_browser__ = __webpack_require__(55);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2_ionic_angular__ = __webpack_require__(9);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__angular_http__ = __webpack_require__(21);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__angular_common__ = __webpack_require__(52);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_component__ = __webpack_require__(560);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__pages_home_home__ = __webpack_require__(220);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__pages_home_postmodal__ = __webpack_require__(666);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__pages_list_list__ = __webpack_require__(61);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__pages_settings_settings__ = __webpack_require__(388);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_10__pages_chat_chat__ = __webpack_require__(222);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_11__pages_profile_profile__ = __webpack_require__(62);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_12__pages_group_group__ = __webpack_require__(667);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_13__pages_siafiles_siafiles__ = __webpack_require__(226);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_14__pages_stream_stream__ = __webpack_require__(390);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_15__pages_mail_mail__ = __webpack_require__(393);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_16__pages_mail_compose__ = __webpack_require__(134);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_17__pages_calendar_calendar__ = __webpack_require__(387);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_18__ionic_native_status_bar__ = __webpack_require__(338);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_19__ionic_native_splash_screen__ = __webpack_require__(341);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_20__ionic_native_qr_scanner__ = __webpack_require__(392);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_21_ngx_qrcode2__ = __webpack_require__(668);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_22__ionic_storage__ = __webpack_require__(42);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_23__graph_service__ = __webpack_require__(26);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_24__bulletinSecret_service__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_25__peer_service__ = __webpack_require__(221);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_26__settings_service__ = __webpack_require__(22);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_27__wallet_service__ = __webpack_require__(24);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_28__transaction_service__ = __webpack_require__(29);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_29__opengraphparser_service__ = __webpack_require__(135);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_30__firebase_service__ = __webpack_require__(224);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_31__pages_sendreceive_sendreceive__ = __webpack_require__(391);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_32__ionic_native_clipboard__ = __webpack_require__(688);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_33__ionic_native_social_sharing__ = __webpack_require__(106);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_34__ionic_native_badge__ = __webpack_require__(379);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_35__ionic_native_deeplinks__ = __webpack_require__(394);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_36__ionic_native_firebase__ = __webpack_require__(386);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_37__ionic_tools_emoji_picker__ = __webpack_require__(689);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_38__ionic_native_file__ = __webpack_require__(731);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_39_ionic2_auto_complete__ = __webpack_require__(380);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_40__autocomplete_provider__ = __webpack_require__(223);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_41__ionic_native_geolocation__ = __webpack_require__(219);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_42__ionic_native_google_maps__ = __webpack_require__(389);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_43__pages_mail_mailitem__ = __webpack_require__(225);
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
                __WEBPACK_IMPORTED_MODULE_31__pages_sendreceive_sendreceive__["a" /* SendReceive */],
                __WEBPACK_IMPORTED_MODULE_10__pages_chat_chat__["a" /* ChatPage */],
                __WEBPACK_IMPORTED_MODULE_11__pages_profile_profile__["a" /* ProfilePage */],
                __WEBPACK_IMPORTED_MODULE_12__pages_group_group__["a" /* GroupPage */],
                __WEBPACK_IMPORTED_MODULE_13__pages_siafiles_siafiles__["a" /* SiaFiles */],
                __WEBPACK_IMPORTED_MODULE_14__pages_stream_stream__["a" /* StreamPage */],
                __WEBPACK_IMPORTED_MODULE_15__pages_mail_mail__["a" /* MailPage */],
                __WEBPACK_IMPORTED_MODULE_16__pages_mail_compose__["a" /* ComposePage */],
                __WEBPACK_IMPORTED_MODULE_17__pages_calendar_calendar__["a" /* CalendarPage */],
                __WEBPACK_IMPORTED_MODULE_43__pages_mail_mailitem__["a" /* MailItemPage */]
            ],
            imports: [
                __WEBPACK_IMPORTED_MODULE_0__angular_platform_browser__["a" /* BrowserModule */],
                __WEBPACK_IMPORTED_MODULE_39_ionic2_auto_complete__["b" /* AutoCompleteModule */],
                __WEBPACK_IMPORTED_MODULE_2_ionic_angular__["e" /* IonicModule */].forRoot(__WEBPACK_IMPORTED_MODULE_5__app_component__["a" /* MyApp */], {}, {
                    links: []
                }),
                __WEBPACK_IMPORTED_MODULE_22__ionic_storage__["a" /* IonicStorageModule */].forRoot({
                    name: '__mydb',
                    driverOrder: ['websql', 'sqlite', 'indexeddb']
                }),
                __WEBPACK_IMPORTED_MODULE_21_ngx_qrcode2__["a" /* NgxQRCodeModule */],
                __WEBPACK_IMPORTED_MODULE_3__angular_http__["c" /* HttpModule */],
                __WEBPACK_IMPORTED_MODULE_37__ionic_tools_emoji_picker__["a" /* EmojiPickerModule */].forRoot(),
                __WEBPACK_IMPORTED_MODULE_4__angular_common__["b" /* CommonModule */]
            ],
            bootstrap: [__WEBPACK_IMPORTED_MODULE_2_ionic_angular__["c" /* IonicApp */]],
            entryComponents: [
                __WEBPACK_IMPORTED_MODULE_5__app_component__["a" /* MyApp */],
                __WEBPACK_IMPORTED_MODULE_6__pages_home_home__["a" /* HomePage */],
                __WEBPACK_IMPORTED_MODULE_7__pages_home_postmodal__["a" /* PostModal */],
                __WEBPACK_IMPORTED_MODULE_8__pages_list_list__["a" /* ListPage */],
                __WEBPACK_IMPORTED_MODULE_9__pages_settings_settings__["a" /* Settings */],
                __WEBPACK_IMPORTED_MODULE_31__pages_sendreceive_sendreceive__["a" /* SendReceive */],
                __WEBPACK_IMPORTED_MODULE_10__pages_chat_chat__["a" /* ChatPage */],
                __WEBPACK_IMPORTED_MODULE_11__pages_profile_profile__["a" /* ProfilePage */],
                __WEBPACK_IMPORTED_MODULE_12__pages_group_group__["a" /* GroupPage */],
                __WEBPACK_IMPORTED_MODULE_13__pages_siafiles_siafiles__["a" /* SiaFiles */],
                __WEBPACK_IMPORTED_MODULE_14__pages_stream_stream__["a" /* StreamPage */],
                __WEBPACK_IMPORTED_MODULE_15__pages_mail_mail__["a" /* MailPage */],
                __WEBPACK_IMPORTED_MODULE_16__pages_mail_compose__["a" /* ComposePage */],
                __WEBPACK_IMPORTED_MODULE_17__pages_calendar_calendar__["a" /* CalendarPage */],
                __WEBPACK_IMPORTED_MODULE_43__pages_mail_mailitem__["a" /* MailItemPage */]
            ],
            providers: [
                __WEBPACK_IMPORTED_MODULE_18__ionic_native_status_bar__["a" /* StatusBar */],
                __WEBPACK_IMPORTED_MODULE_19__ionic_native_splash_screen__["a" /* SplashScreen */],
                { provide: __WEBPACK_IMPORTED_MODULE_1__angular_core__["v" /* ErrorHandler */], useClass: __WEBPACK_IMPORTED_MODULE_2_ionic_angular__["d" /* IonicErrorHandler */] },
                __WEBPACK_IMPORTED_MODULE_20__ionic_native_qr_scanner__["a" /* QRScanner */],
                __WEBPACK_IMPORTED_MODULE_21_ngx_qrcode2__["a" /* NgxQRCodeModule */],
                __WEBPACK_IMPORTED_MODULE_23__graph_service__["a" /* GraphService */],
                __WEBPACK_IMPORTED_MODULE_24__bulletinSecret_service__["a" /* BulletinSecretService */],
                __WEBPACK_IMPORTED_MODULE_25__peer_service__["a" /* PeerService */],
                __WEBPACK_IMPORTED_MODULE_26__settings_service__["a" /* SettingsService */],
                __WEBPACK_IMPORTED_MODULE_27__wallet_service__["a" /* WalletService */],
                __WEBPACK_IMPORTED_MODULE_28__transaction_service__["a" /* TransactionService */],
                __WEBPACK_IMPORTED_MODULE_29__opengraphparser_service__["a" /* OpenGraphParserService */],
                __WEBPACK_IMPORTED_MODULE_32__ionic_native_clipboard__["a" /* Clipboard */],
                __WEBPACK_IMPORTED_MODULE_33__ionic_native_social_sharing__["a" /* SocialSharing */],
                __WEBPACK_IMPORTED_MODULE_34__ionic_native_badge__["a" /* Badge */],
                __WEBPACK_IMPORTED_MODULE_35__ionic_native_deeplinks__["a" /* Deeplinks */],
                __WEBPACK_IMPORTED_MODULE_36__ionic_native_firebase__["a" /* Firebase */],
                __WEBPACK_IMPORTED_MODULE_30__firebase_service__["a" /* FirebaseService */],
                __WEBPACK_IMPORTED_MODULE_38__ionic_native_file__["a" /* File */],
                __WEBPACK_IMPORTED_MODULE_40__autocomplete_provider__["a" /* CompleteTestService */],
                __WEBPACK_IMPORTED_MODULE_39_ionic2_auto_complete__["a" /* AutoCompleteComponent */],
                __WEBPACK_IMPORTED_MODULE_41__ionic_native_geolocation__["a" /* Geolocation */],
                __WEBPACK_IMPORTED_MODULE_42__ionic_native_google_maps__["a" /* GoogleMaps */]
            ]
        })
    ], AppModule);
    return AppModule;
}());

//# sourceMappingURL=app.module.js.map

/***/ }),

/***/ 560:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return MyApp; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(9);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__ionic_native_status_bar__ = __webpack_require__(338);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__ionic_native_splash_screen__ = __webpack_require__(341);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__graph_service__ = __webpack_require__(26);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__settings_service__ = __webpack_require__(22);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__bulletinSecret_service__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__wallet_service__ = __webpack_require__(24);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__pages_home_home__ = __webpack_require__(220);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__pages_list_list__ = __webpack_require__(61);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_10__pages_calendar_calendar__ = __webpack_require__(387);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_11__pages_settings_settings__ = __webpack_require__(388);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_12__pages_siafiles_siafiles__ = __webpack_require__(226);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_13__pages_stream_stream__ = __webpack_require__(390);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_14__pages_sendreceive_sendreceive__ = __webpack_require__(391);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_15__pages_profile_profile__ = __webpack_require__(62);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_16__pages_mail_mail__ = __webpack_require__(393);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_17__ionic_native_deeplinks__ = __webpack_require__(394);
var __assign = (this && this.__assign) || function () {
    __assign = Object.assign || function(t) {
        for (var s, i = 1, n = arguments.length; i < n; i++) {
            s = arguments[i];
            for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p))
                t[p] = s[p];
        }
        return t;
    };
    return __assign.apply(this, arguments);
};
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
    function MyApp(platform, statusBar, splashScreen, walletService, graphService, settingsService, bulletinSecretService, events, deeplinks) {
        var _this = this;
        this.platform = platform;
        this.statusBar = statusBar;
        this.splashScreen = splashScreen;
        this.walletService = walletService;
        this.graphService = graphService;
        this.settingsService = settingsService;
        this.bulletinSecretService = bulletinSecretService;
        this.events = events;
        this.deeplinks = deeplinks;
        events.subscribe('graph', function () {
            _this.rootPage = __WEBPACK_IMPORTED_MODULE_8__pages_home_home__["a" /* HomePage */];
        });
        events.subscribe('menu', function (options) {
            _this.root = _this.pages[0].root;
            _this.setMenu(options);
            _this.openPage(_this.pages[0]);
        });
        events.subscribe('menuonly', function (options) {
            _this.root = _this.pages[0].root;
            _this.setMenu(options);
        });
        this.rootPage = __WEBPACK_IMPORTED_MODULE_11__pages_settings_settings__["a" /* Settings */];
    }
    MyApp.prototype.ngAfterViewInit = function () {
        this.initializeApp();
    };
    MyApp.prototype.setMenu = function (pages) {
        if (pages === void 0) { pages = null; }
        if (pages) {
            this.pages = pages;
            return;
        }
        if (this.settingsService.menu == 'home') {
            this.pages = [
                { title: 'Home', label: 'Home', component: __WEBPACK_IMPORTED_MODULE_8__pages_home_home__["a" /* HomePage */], count: false, color: '', root: true },
            ];
        }
        else if (this.settingsService.menu == 'mail') {
            this.pages = [
                { title: 'Inbox', label: 'Inbox', component: __WEBPACK_IMPORTED_MODULE_16__pages_mail_mail__["a" /* MailPage */], count: false, color: '', root: true },
                { title: 'Sent', label: 'Sent', component: __WEBPACK_IMPORTED_MODULE_16__pages_mail_mail__["a" /* MailPage */], count: false, color: '', root: true },
            ];
        }
        else if (this.settingsService.menu == 'chat') {
            this.pages = [
                { title: 'Messages', label: 'Chat', component: __WEBPACK_IMPORTED_MODULE_9__pages_list_list__["a" /* ListPage */], count: false, color: '', root: true },
            ];
        }
        else if (this.settingsService.menu == 'community') {
            this.pages = [
                { title: 'Community', label: 'Community', component: __WEBPACK_IMPORTED_MODULE_9__pages_list_list__["a" /* ListPage */], count: false, color: '', root: true },
            ];
        }
        else if (this.settingsService.menu == 'calendar') {
            this.pages = [
                { title: 'Calendar', label: 'Calendar', component: __WEBPACK_IMPORTED_MODULE_10__pages_calendar_calendar__["a" /* CalendarPage */], count: false, color: '', root: true },
            ];
        }
        else if (this.settingsService.menu == 'contacts') {
            this.pages = [
                { title: 'Contacts', label: 'Contacts', component: __WEBPACK_IMPORTED_MODULE_9__pages_list_list__["a" /* ListPage */], count: false, color: '', root: true },
                { title: 'Contact Requests', label: 'Contact Requests', component: __WEBPACK_IMPORTED_MODULE_9__pages_list_list__["a" /* ListPage */], count: false, color: '', root: true },
                { title: 'Groups', label: 'Groups', component: __WEBPACK_IMPORTED_MODULE_9__pages_list_list__["a" /* ListPage */], count: false, color: '', root: true },
            ];
        }
        else if (this.settingsService.menu == 'files') {
            this.pages = [
                { title: 'Files', label: 'Files', component: __WEBPACK_IMPORTED_MODULE_12__pages_siafiles_siafiles__["a" /* SiaFiles */], count: false, color: '', root: true },
            ];
        }
        else if (this.settingsService.menu == 'wallet') {
            this.pages = [
                { title: 'Send / Receive', label: 'Send / Receive', component: __WEBPACK_IMPORTED_MODULE_14__pages_sendreceive_sendreceive__["a" /* SendReceive */], count: false, color: '', root: true }
            ];
        }
        else if (this.settingsService.menu == 'stream') {
            this.pages = [
                { title: 'Stream', label: 'Stream', component: __WEBPACK_IMPORTED_MODULE_13__pages_stream_stream__["a" /* StreamPage */], count: false, color: '', root: true }
            ];
        }
        else if (this.settingsService.menu == 'settings') {
            this.pages = [
                { title: 'Settings', label: 'Identity', component: __WEBPACK_IMPORTED_MODULE_11__pages_settings_settings__["a" /* Settings */], count: false, color: '', root: true },
                { title: 'Profile', label: 'Profile', component: __WEBPACK_IMPORTED_MODULE_15__pages_profile_profile__["a" /* ProfilePage */], count: false, color: '', root: true }
            ];
        }
        this.openPage(this.pages[0]);
    };
    MyApp.prototype.initializeApp = function () {
        var _this = this;
        this.platform.ready()
            .then(function () {
            if (_this.platform.is('cordova')) {
                _this.deeplinks.routeWithNavController(_this.nav, {
                    '/app': __WEBPACK_IMPORTED_MODULE_11__pages_settings_settings__["a" /* Settings */]
                }).subscribe(function (match) {
                    // match.$route - the route we matched, which is the matched entry from the arguments to route()
                    // match.$args - the args passed in the link
                    // match.$link - the full link data
                    console.log('Successfully matched route', match);
                }, function (nomatch) {
                    // nomatch.$link - the full link data
                    console.error('Got a deeplink that didn\'t match', nomatch);
                });
            }
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
        if (page.root) {
            this.nav.setRoot(page.component, __assign({ pageTitle: page }, page.kwargs));
        }
        else {
            this.nav.push(page.component, __assign({ pageTitle: page }, page.kwargs));
        }
    };
    MyApp.prototype.segmentChanged = function (e) {
        this.settingsService.menu = e.value;
        this.setMenu();
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
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["n" /* Component */])({template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/app/app.html"*/'<ion-split-pane>\n  <ion-menu [content]="content">\n    <ion-header>\n      <ion-toolbar>\n        <ion-title>\n          <ion-note *ngIf="settingsService.remoteSettings.restricted" style="font-size: 20px">\n            {{bulletinSecretService.identity.username || \'Center Identity\'}}\n          </ion-note>\n          <ion-note *ngIf="!settingsService.remoteSettings.restricted" style="font-size: 20px">\n            {{bulletinSecretService.identity.username || \'YadaCoin\'}}\n          </ion-note>\n          <ion-note style="font-size: 12px">\n            {{version}}\n          </ion-note>\n        </ion-title>\n      </ion-toolbar>\n    </ion-header>\n\n    <ion-content>\n      <ion-list *ngIf="bulletinSecretService.key">\n        <ng-container>\n          <ion-segment (ionChange)="segmentChanged($event)" [(ngModel)]="settingsService.menu">\n            <ion-segment-button value="home" title="home">\n              <ion-icon name="home"></ion-icon>\n            </ion-segment-button>\n            <ion-segment-button value="wallet" title="wallet">\n              <ion-icon name="cash"></ion-icon>\n            </ion-segment-button>\n            <ion-segment-button value="mail" title="mail">\n              <ion-icon name="mail"></ion-icon>\n            </ion-segment-button>\n            <ion-segment-button value="chat" title="private messages">\n              <ion-icon name="chatboxes"></ion-icon>\n            </ion-segment-button>\n            <ion-segment-button value="community" title="community chat">\n              <ion-icon name="people"></ion-icon>\n            </ion-segment-button>\n            <ion-segment-button value="calendar" title="calendar">\n              <ion-icon name="calendar"></ion-icon>\n            </ion-segment-button>\n            <ion-segment-button value="contacts" title="contacts">\n              <ion-icon name="contacts"></ion-icon>\n            </ion-segment-button>\n            <ion-segment-button value="files" title="files" *ngIf="settingsService.remoteSettings.restricted">\n              <ion-icon name="folder"></ion-icon>\n            </ion-segment-button>\n            <ion-segment-button value="settings" title="identity">\n              <ion-icon name="contact"></ion-icon>\n            </ion-segment-button>\n          </ion-segment>\n        </ng-container>\n        <ng-container *ngFor="let p of pages">\n          <button \n            menuClose \n            ion-item \n            (click)="openPage(p)"\n            [color]="graphService.friend_request_count > 0 ? \'primary\' : \'grey\'"\n            *ngIf="p.title == \'Contact Requests\'"\n          >\n            {{p.label}}\n          </button>\n          <button \n            menuClose \n            ion-item \n            (click)="openPage(p)"\n            [color]="\'grey\'"\n            *ngIf="p.title == \'Messages\'"\n          >\n            {{p.label}}\n          </button>\n          <button \n            menuClose \n            ion-item \n            (click)="openPage(p)"\n            *ngIf="[\'Messages\', \'Contact Requests\'].indexOf(p.title) < 0"\n          >\n            {{p.label}}\n          </button>\n        </ng-container>\n      </ion-list>\n      <img *ngIf="!settingsService.remoteSettings.restricted" src="assets/img/yadacoinlogosmall.png" class="logo">\n      <img *ngIf="settingsService.remoteSettings.restricted" src="assets/center-identity-logo-square.png" class="logo">\n    </ion-content>\n\n  </ion-menu>\n  <!-- Disable swipe-to-go-back because it\'s poor UX to combine STGB with side menus -->\n  <ion-nav [root]="rootPage" main #content swipeBackEnabled="false"></ion-nav>\n</ion-split-pane>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/app/app.html"*/
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["k" /* Platform */],
            __WEBPACK_IMPORTED_MODULE_2__ionic_native_status_bar__["a" /* StatusBar */],
            __WEBPACK_IMPORTED_MODULE_3__ionic_native_splash_screen__["a" /* SplashScreen */],
            __WEBPACK_IMPORTED_MODULE_7__wallet_service__["a" /* WalletService */],
            __WEBPACK_IMPORTED_MODULE_4__graph_service__["a" /* GraphService */],
            __WEBPACK_IMPORTED_MODULE_5__settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_6__bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["b" /* Events */],
            __WEBPACK_IMPORTED_MODULE_17__ionic_native_deeplinks__["a" /* Deeplinks */]])
    ], MyApp);
    return MyApp;
}());

//# sourceMappingURL=app.component.js.map

/***/ }),

/***/ 606:
/***/ (function(module, exports) {

/* (ignored) */

/***/ }),

/***/ 607:
/***/ (function(module, exports) {

/* (ignored) */

/***/ }),

/***/ 61:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return ListPage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(9);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__ionic_storage__ = __webpack_require__(42);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_graph_service__ = __webpack_require__(26);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_bulletinSecret_service__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_wallet_service__ = __webpack_require__(24);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_transaction_service__ = __webpack_require__(29);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__app_settings_service__ = __webpack_require__(22);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__ionic_native_social_sharing__ = __webpack_require__(106);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__chat_chat__ = __webpack_require__(222);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_10__profile_profile__ = __webpack_require__(62);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_11__angular_http__ = __webpack_require__(21);
var __assign = (this && this.__assign) || function () {
    __assign = Object.assign || function(t) {
        for (var s, i = 1, n = arguments.length; i < n; i++) {
            s = arguments[i];
            for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p))
                t[p] = s[p];
        }
        return t;
    };
    return __assign.apply(this, arguments);
};
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
    function ListPage(navCtrl, navParams, storage, graphService, bulletinSecretService, walletService, transactionService, socialSharing, alertCtrl, loadingCtrl, events, ahttp, settingsService, toastCtrl) {
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
        this.toastCtrl = toastCtrl;
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
    ListPage.prototype.createGroup = function () {
        var _this = this;
        this.graphService.getInfo()
            .then(function () {
            return new Promise(function (resolve, reject) {
                var alert = _this.alertCtrl.create({
                    title: 'Group name',
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
            .then(function (groupName) {
            return _this.graphService.createGroup(groupName);
        })
            .then(function (hash) {
            if (_this.settingsService.remoteSettings['walletUrl']) {
                return _this.graphService.getInfo();
            }
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
                var public_key = '';
                var graphArray = [];
                if (_this.pageTitle == 'Contacts') {
                    graphArray = _this.graphService.graph.friends.filter(function (item) { return !!item.relationship.identity; });
                    graphArray = _this.getDistinctFriends(graphArray).friend_list;
                    graphArray.sort(function (a, b) {
                        if (a.relationship.identity.username.toLowerCase() < b.relationship.identity.username.toLowerCase())
                            return -1;
                        if (a.relationship.identity.username.toLowerCase() > b.relationship.identity.username.toLowerCase())
                            return 1;
                        return 0;
                    });
                    _this.makeList(graphArray, 'Contacts', null);
                    _this.loading = false;
                }
                else if (_this.pageTitle == 'Groups') {
                    for (var i = 0; i < _this.graphService.graph.groups.length; i++) {
                        if (!_this.graphService.graph.groups[i].relationship.parent) {
                            graphArray.push(_this.graphService.graph.groups[i]);
                        }
                    }
                    graphArray.sort(function (a, b) {
                        if (a.relationship.username.toLowerCase() < b.relationship.username.toLowerCase())
                            return -1;
                        if (a.relationship.username.toLowerCase() > b.relationship.username.toLowerCase())
                            return 1;
                        return 0;
                    });
                    _this.makeList(graphArray, 'Groups', null);
                    _this.loading = false;
                }
                else if (_this.pageTitle == 'Messages') {
                    public_key = _this.bulletinSecretService.key.getPublicKeyBuffer().toString('hex');
                    return _this.graphService.getNewMessages()
                        .then(function (graphArray) {
                        var messages = _this.markNew(public_key, graphArray, _this.graphService.new_messages_counts);
                        var friendsWithMessagesList = _this.getDistinctFriends(messages);
                        _this.populateRemainingFriends(friendsWithMessagesList.friend_list, friendsWithMessagesList.used_rids);
                        _this.loading = false;
                        friendsWithMessagesList.friend_list.sort(function (a, b) {
                            try {
                                var ausername = a.relationship.identity ? a.relationship.identity.username : a.relationship.username;
                                var busername = b.relationship.identity ? b.relationship.identity.username : b.relationship.username;
                                if (ausername.toLowerCase() < busername.toLowerCase())
                                    return -1;
                                if (ausername.toLowerCase() > busername.toLowerCase())
                                    return 1;
                                return 0;
                            }
                            catch (err) {
                                return 0;
                            }
                        });
                        return _this.makeList(friendsWithMessagesList.friend_list, '', { title: 'Messages', component: __WEBPACK_IMPORTED_MODULE_9__chat_chat__["a" /* ChatPage */] })
                            .then(function (pages) {
                            _this.events.publish('menu', pages);
                        });
                    }).catch(function (err) {
                        console.log(err);
                    });
                }
                else if (_this.pageTitle == 'Community') {
                    public_key = _this.bulletinSecretService.key.getPublicKeyBuffer().toString('hex');
                    return _this.graphService.getNewMessages()
                        .then(function (graphArray) {
                        var messages = _this.markNew(public_key, graphArray, _this.graphService.new_messages_counts);
                        var friendsWithMessagesList = _this.getDistinctFriends(messages);
                        _this.populateRemainingGroups(friendsWithMessagesList.friend_list, friendsWithMessagesList.used_rids);
                        _this.loading = false;
                        friendsWithMessagesList.friend_list.sort(function (a, b) {
                            try {
                                var ausername = a.relationship.identity ? a.relationship.identity.username : a.relationship.username;
                                var busername = b.relationship.identity ? b.relationship.identity.username : b.relationship.username;
                                if (ausername.toLowerCase() < busername.toLowerCase())
                                    return -1;
                                if (ausername.toLowerCase() > busername.toLowerCase())
                                    return 1;
                                return 0;
                            }
                            catch (err) {
                                return 0;
                            }
                        });
                        return _this.makeList(friendsWithMessagesList.friend_list, '', { title: 'Community', component: __WEBPACK_IMPORTED_MODULE_9__chat_chat__["a" /* ChatPage */] })
                            .then(function (pages) {
                            _this.events.publish('menu', pages);
                            _this.loading = false;
                        });
                    }).catch(function (err) {
                        console.log(err);
                    });
                }
                else if (_this.pageTitle == 'Sent') {
                    public_key = _this.bulletinSecretService.key.getPublicKeyBuffer().toString('hex');
                    return _this.graphService.getSentMessages()
                        .then(function (graphArray) {
                        var messages = _this.markNew(public_key, graphArray, _this.graphService.new_messages_counts);
                        var friendsWithMessagesList = _this.getDistinctFriends(messages);
                        _this.populateRemainingFriends(friendsWithMessagesList.friend_list, friendsWithMessagesList.used_rids);
                        _this.loading = false;
                        friendsWithMessagesList.friend_list.sort(function (a, b) {
                            if (a.relationship.identity.username.toLowerCase() < b.relationship.identity.username.toLowerCase())
                                return -1;
                            if (a.relationship.identity.username.toLowerCase() > b.relationship.identity.username.toLowerCase())
                                return 1;
                            return 0;
                        });
                        return _this.makeList(friendsWithMessagesList.friend_list, 'Messages', null);
                    }).catch(function (err) {
                        console.log(err);
                    });
                }
                else if (_this.pageTitle == 'Sign Ins') {
                    public_key = _this.bulletinSecretService.key.getPublicKeyBuffer().toString('hex');
                    return _this.graphService.getNewSignIns()
                        .then(function (graphArray) {
                        var sign_ins = _this.markNew(public_key, graphArray, _this.graphService.new_sign_ins_counts);
                        var friendsWithSignInsList = _this.getDistinctFriends(sign_ins);
                        _this.populateRemainingFriends(friendsWithSignInsList.friend_list, friendsWithSignInsList.used_rids);
                        _this.loading = false;
                        return _this.makeList(friendsWithSignInsList.friend_list, 'Sing Ins', null);
                    }).catch(function () {
                        console.log('listpage getFriends or getNewSignIns error');
                    });
                }
                else if (_this.pageTitle == 'Contact Requests') {
                    return _this.graphService.getFriendRequests()
                        .then(function () {
                        var graphArray = _this.graphService.graph.friend_requests;
                        graphArray.sort(function (a, b) {
                            if (a.relationship.identity.username.toLowerCase() < b.relationship.identity.username.toLowerCase())
                                return -1;
                            if (a.relationship.identity.username.toLowerCase() > b.relationship.identity.username.toLowerCase())
                                return 1;
                            return 0;
                        });
                        _this.loading = false;
                        return _this.makeList(graphArray, 'Contact Requests', null);
                    }).catch(function () {
                        console.log('listpage getFriendRequests error');
                    });
                }
                else if (_this.pageTitle == 'Sent Requests') {
                    return _this.graphService.getSentFriendRequests()
                        .then(function () {
                        var graphArray = _this.graphService.graph.sent_friend_requests;
                        graphArray.sort(function (a, b) {
                            if (a.relationship.identity.username.toLowerCase() < b.relationship.identity.username.toLowerCase())
                                return -1;
                            if (a.relationship.identity.username.toLowerCase() > b.relationship.identity.username.toLowerCase())
                                return 1;
                            return 0;
                        });
                        _this.loading = false;
                        return _this.makeList(graphArray, 'Sent Requests', null);
                    }).catch(function () {
                        console.log('listpage getSentFriendRequests error');
                    });
                }
                else if (_this.pageTitle == 'Reacts Detail') {
                    graphArray = _this.navParams.get('detail');
                    _this.loading = false;
                    return _this.makeList(graphArray, 'Reacts Detail', null);
                }
                else if (_this.pageTitle == 'Comment Reacts Detail') {
                    graphArray = _this.navParams.get('detail');
                    _this.loading = false;
                    return _this.makeList(graphArray, 'Comment Reacts Detail', null);
                }
            }
            else {
                _this.loading = false;
                _this.loadingBalance = false;
                if (_this.pageTitle == 'Sent Requests') {
                    resolve();
                }
                else if (_this.pageTitle == 'Contact Requests') {
                    _this.friend_request = _this.navParams.get('item').identity;
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
                        reject('listpage getSignIns error');
                    });
                }
            }
        });
    };
    ListPage.prototype.markNew = function (public_key, graphArray, graphCount) {
        var collection = [];
        for (var i in graphArray) {
            if (public_key !== graphArray[i]['public_key'] && graphCount[i] && graphCount[i] < graphArray[i]['height']) {
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
            if (!this.graphService.friends_indexed[item.rid]) {
                continue;
            }
            if (used_rids.indexOf(this.graphService.friends_indexed[item.rid]) === -1) {
                friend_list.push(item);
                used_rids.push(this.graphService.friends_indexed[item.rid]);
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
        var friend_list = [];
        var used_rids = [];
        for (var i = 0; i < collection.length; i++) {
            // we could have multiple transactions per friendship
            // so make sure we're going using the rid once
            var item = collection[i];
            if (!this.graphService.groups_indexed[item.requested_rid]) {
                continue;
            }
            if (used_rids.indexOf(this.graphService.groups_indexed[item.requested_rid]) === -1) {
                friend_list.push(item);
                used_rids.push(this.graphService.groups_indexed[item.requested_rid]);
            }
        }
        return {
            friend_list: friend_list,
            used_rids: used_rids
        };
    };
    ListPage.prototype.populateRemainingFriends = function (friend_list, used_rids) {
        // now add everyone else
        var friendsAndGroupsList = this.graphService.graph.friends;
        for (var i = 0; i < friendsAndGroupsList.length; i++) {
            var rid = void 0;
            if (this.graphService.groups_indexed[friendsAndGroupsList[i].requested_rid]) {
                rid = friendsAndGroupsList[i].requested_rid;
            }
            else {
                rid = friendsAndGroupsList[i].rid;
            }
            if (used_rids.indexOf(rid) === -1) {
                friend_list.push(friendsAndGroupsList[i]);
                used_rids.push(rid);
            }
        }
    };
    ListPage.prototype.populateRemainingGroups = function (friend_list, used_rids) {
        // now add everyone else
        var friendsAndGroupsList = this.graphService.graph.groups;
        for (var i = 0; i < friendsAndGroupsList.length; i++) {
            var rid = void 0;
            if (this.graphService.groups_indexed[friendsAndGroupsList[i].requested_rid]) {
                rid = friendsAndGroupsList[i].requested_rid;
            }
            else {
                rid = friendsAndGroupsList[i].rid;
            }
            if (used_rids.indexOf(rid) === -1) {
                friend_list.push(friendsAndGroupsList[i]);
                used_rids.push(rid);
            }
        }
    };
    ListPage.prototype.makeList = function (graphArray, pageTitle, page) {
        var _this = this;
        return new Promise(function (resolve, reject) {
            var items = [];
            _this.items = [];
            for (var i = 0; i < graphArray.length; i++) {
                if (page) {
                    items.push({ title: page.title, label: graphArray[i].relationship.identity ? graphArray[i].relationship.identity.username : graphArray[i].relationship.username, component: page.component, count: false, color: '', kwargs: { identity: graphArray[i].relationship.identity || graphArray[i].relationship }, root: true });
                }
                else {
                    _this.items.push({ pageTitle: pageTitle, identity: graphArray[i].relationship });
                }
            }
            resolve(items);
        });
    };
    ListPage.prototype.newChat = function () {
        var item = { pageTitle: { title: "Friends" }, context: 'newChat' };
        this.navCtrl.push(ListPage_1, item);
    };
    ListPage.prototype.itemTapped = function (event, item) {
        if (this.pageTitle == 'Messages') {
            this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_9__chat_chat__["a" /* ChatPage */], __assign({}, item));
        }
        else if (this.pageTitle == 'Community') {
            this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_9__chat_chat__["a" /* ChatPage */], __assign({}, item));
        }
        else if (this.pageTitle == 'Groups') {
            this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_10__profile_profile__["a" /* ProfilePage */], __assign({}, item));
        }
        else if (this.pageTitle == 'Contacts') {
            this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_10__profile_profile__["a" /* ProfilePage */], __assign({}, item.identity));
        }
        else {
            this.navCtrl.push(ListPage_1, {
                item: item
            });
        }
    };
    ListPage.prototype.accept = function () {
        var _this = this;
        var rids = this.graphService.generateRids(this.friend_request.identity);
        return this.graphService.addFriend(this.friend_request.identity, rids.rid, rids.requester_rid, rids.requested_rid).then(function (txn) {
            return _this.graphService.getFriendRequests();
        })
            .then(function () {
            var alert = _this.alertCtrl.create();
            alert.setTitle('Friend Accept Sent');
            alert.setSubTitle('Your Friend Request acceptance has been submitted successfully.');
            alert.addButton('Ok');
            alert.present();
            _this.navCtrl.setRoot(ListPage_1, { pageTitle: { title: 'Contacts', label: 'Contacts', component: ListPage_1, count: false, color: '' } });
        }).catch(function (err) {
            console.log(err);
        });
    };
    ListPage.prototype.addFriend = function () {
        var _this = this;
        var buttons = [];
        buttons.push({
            text: 'Add',
            handler: function (data) {
                var promise;
                if (_this.settingsService.remoteSettings.restricted) {
                    promise = _this.graphService.addFriendFromSkylink(data.identity);
                }
                else {
                    promise = _this.graphService.addFriend(JSON.parse(data.identity));
                }
                promise
                    .then(function () {
                    var alert = _this.alertCtrl.create();
                    alert.setTitle('Contact added');
                    alert.setSubTitle('Your contact was added successfully');
                    alert.addButton('Ok');
                    alert.present();
                    return _this.choosePage();
                });
            }
        });
        var alert = this.alertCtrl.create({
            inputs: [
                {
                    name: 'identity',
                    placeholder: 'Paste identity here...'
                }
            ],
            buttons: buttons
        });
        alert.setTitle('Request contact');
        alert.setSubTitle('Paste the identity of your contact below');
        alert.present();
    };
    ListPage.prototype.addGroup = function () {
        var _this = this;
        var buttons = [];
        buttons.push({
            text: 'Add',
            handler: function (data) {
                var promise;
                if (_this.settingsService.remoteSettings.restricted) {
                    promise = _this.graphService.addGroupFromSkylink(data.identity);
                }
                else {
                    promise = _this.graphService.addGroup(JSON.parse(data.identity));
                }
                promise
                    .then(function () {
                    var alert = _this.alertCtrl.create();
                    alert.setTitle('Group added');
                    alert.setSubTitle('Your group was added successfully');
                    alert.addButton('Ok');
                    alert.present();
                    return _this.choosePage();
                });
            }
        });
        var alert = this.alertCtrl.create({
            inputs: [
                {
                    name: 'identity',
                    placeholder: 'Paste identity here...'
                }
            ],
            buttons: buttons
        });
        alert.setTitle('Add group');
        alert.setSubTitle('Paste the identity of your contact below');
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
            selector: 'page-list',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/list/list.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n    <ion-title *ngIf="loading">Loading...</ion-title>\n    <ion-title *ngIf="!loading">{{label}}</ion-title>\n  </ion-navbar>\n</ion-header>\n\n<ion-content>\n  <ion-refresher (ionRefresh)="refresh($event)">\n    <ion-refresher-content></ion-refresher-content>\n  </ion-refresher>\n  <ion-spinner *ngIf="loading"></ion-spinner>\n  <button *ngIf="pageTitle ==\'Contacts\'" ion-button secondary (click)="addFriend()">Add contact</button>\n  <button *ngIf="pageTitle ==\'Groups\'" ion-button secondary (click)="addGroup()">Add group</button>\n  <button *ngIf="pageTitle ==\'Groups\'" ion-button secondary (click)="createGroup()">Create group</button>\n  <ion-card *ngIf="items && items.length == 0">\n      <ion-card-content>\n        <ion-card-title style="text-overflow:ellipsis;" text-wrap>\n          No items to display.\n      </ion-card-title>\n    </ion-card-content>\n  </ion-card>\n  <ion-list>\n    <button ion-item *ngFor="let item of items" (click)="itemTapped($event, item)">\n      <span *ngIf="pageTitle ==\'Groups\'">{{item.identity.username}}</span>\n      <span *ngIf="pageTitle ==\'Contact Requests\'">{{item.identity.identity.username}}</span>\n      <span *ngIf="pageTitle ==\'Messages\' && !identity.new && !identity.parent && identity.username">{{ identity.username}}</span>\n      <span *ngIf="pageTitle ==\'Messages\' && !identity.new && identity.parent"><ion-note>&nbsp;&nbsp;&nbsp;&nbsp;{{identity.username}}</ion-note></span>\n      <span *ngIf="pageTitle ==\'Community\' && !identity.new && !identity.parent && identity.username">{{ identity.username}}</span>\n      <span *ngIf="pageTitle ==\'Community\' && !identity.new && identity.parent"><ion-note>&nbsp;&nbsp;&nbsp;&nbsp;{{identity.username}}</ion-note></span>\n      <span *ngIf="pageTitle ==\'Chat\' && identity.new"><strong>{{identity.username}}</strong></span>\n      <span *ngIf="pageTitle ==\'Contacts\'">{{item.identity.identity.username}}</span>\n    </button>\n  </ion-list>\n  <div *ngIf="selectedItem && pageTitle ==\'Sent Requests\'" padding>\n  </div>\n  <div *ngIf="selectedItem && pageTitle ==\'Contact Requests\'" padding>\n\n    <ion-card *ngIf="friend_request">\n      <ion-card-header>\n        <p><strong>New contact request from {{friend_request.identity.username}}</strong> </p>\n      </ion-card-header>\n      <ion-card-content>\n        <p>{{friend_request.identity.username}} would like to be added as a contact</p>\n        <button ion-button secondary (click)="accept()">Accept</button>\n      </ion-card-content>\n    </ion-card>\n    <!-- for now, we can\'t do p2p on WKWebView\n    <button *ngIf="pageTitle == \'Contact Requests\'" ion-button secondary (click)="accept(selectedItem.transaction)">Accept Request</button>\n\n    <button *ngIf="pageTitle == \'Contact Requests\'" ion-button secondary (click)="send_receipt(selectedItem.transaction)">Send Receipt</button>\n    -->\n  </div>\n  <div *ngIf="selectedItem && pageTitle ==\'Contacts\'" padding>\n    You navigated here from <b>{{selectedItem.transaction.rid}}</b>\n  </div>\n  <div *ngIf="selectedItem && pageTitle ==\'Posts\'" padding>\n    <a href="{{selectedItem.transaction.relationship.postText}}" target="_blank">{{selectedItem.transaction.relationship.postText}}</a>\n  </div>\n  <div *ngIf="selectedItem && pageTitle ==\'Sign Ins\'" padding>\n\n    <ion-card>\n      <ion-card-header>\n        <p><strong>{{selectedItem.transaction.identity.username}}</strong> has sent you an authorization offer. Accept offer with the \'Sign in\' button.</p>\n      </ion-card-header>\n      <ion-card-content>\n        <button ion-button secondary (click)="sendSignIn()">Sign in</button>\n        Sign in code: {{signInText}}\n      </ion-card-content>\n    </ion-card>\n    <!-- for now, we can\'t do p2p on WKWebView\n    <button *ngIf="pageTitle == \'Contact Requests\'" ion-button secondary (click)="accept(selectedItem.transaction)">Accept Request</button>\n\n    <button *ngIf="pageTitle == \'Contact Requests\'" ion-button secondary (click)="send_receipt(selectedItem.transaction)">Send Receipt</button>\n    -->\n  </div>\n</ion-content>\n'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/list/list.html"*/
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
            __WEBPACK_IMPORTED_MODULE_11__angular_http__["b" /* Http */],
            __WEBPACK_IMPORTED_MODULE_7__app_settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["l" /* ToastController */]])
    ], ListPage);
    return ListPage;
}());

//# sourceMappingURL=list.js.map

/***/ }),

/***/ 62:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return ProfilePage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(9);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__ionic_storage__ = __webpack_require__(42);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_graph_service__ = __webpack_require__(26);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_bulletinSecret_service__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_wallet_service__ = __webpack_require__(24);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_transaction_service__ = __webpack_require__(29);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__list_list__ = __webpack_require__(61);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__chat_chat__ = __webpack_require__(222);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__angular_http__ = __webpack_require__(21);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_10__app_settings_service__ = __webpack_require__(22);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_11__mail_compose__ = __webpack_require__(134);
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
        var _this = this;
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
        this.subgroups = [];
        this.identity = this.navParams.get('identity');
        var rids = this.graphService.generateRids(this.identity);
        this.rid = rids.rid;
        this.requested_rid = rids.requested_rid;
        this.requester_rid = rids.requester_rid;
        if (this.settingsService.remoteSettings.restricted) {
            this.busy = true;
            this.graphService.identityToSkylink(this.identity)
                .then(function (skylink) {
                _this.identitySkylink = skylink;
                _this.busy = false;
            });
        }
        else {
            this.identityJson = JSON.stringify(this.graphService.toIdentity(this.identity), null, 4);
        }
        this.isAdded = this.graphService.isAdded(this.identity);
        this.group = this.graphService.isGroup(this.identity);
    }
    ProfilePage_1 = ProfilePage;
    ProfilePage.prototype.invite = function () {
        var alert = this.alertCtrl.create();
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
        this.graphService.graph.friends.map(function (friend) {
            return friend;
        });
        alert.present();
    };
    ProfilePage.prototype.addFriend = function () {
        var _this = this;
        var info;
        var buttons = [];
        buttons.push({
            text: 'Add',
            handler: function (data) {
                return _this.graphService.addFriend(_this.identity)
                    .then(function (txn) {
                    var alert = _this.alertCtrl.create();
                    alert.setTitle('Contact Request Sent');
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
        alert.setTitle('Add contact');
        alert.setSubTitle('Do you want to add ' + this.identity.username + '?');
        alert.present();
    };
    ProfilePage.prototype.createSubGroup = function () {
        var _this = this;
        this.graphService.getInfo()
            .then(function () {
            return new Promise(function (resolve, reject) {
                var alert = _this.alertCtrl.create({
                    title: 'Sub-group name',
                    inputs: [
                        {
                            name: 'groupname',
                            placeholder: 'Sub-group name'
                        }
                    ],
                    buttons: [
                        {
                            text: 'Save',
                            handler: function (data) {
                                var toast = _this.toastCtrl.create({
                                    message: 'Sub-group created',
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
            .then(function (groupName) {
            return _this.graphService.createGroup(groupName, _this.item);
        })
            .then(function (hash) {
            if (_this.settingsService.remoteSettings['walletUrl']) {
                return _this.graphService.getInfo();
            }
        });
    };
    ProfilePage.prototype.message = function () {
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_8__chat_chat__["a" /* ChatPage */], {
            identity: this.identity
        });
    };
    ProfilePage.prototype.openSubGroup = function (subGroup) {
        this.navCtrl.push(ProfilePage_1, {
            item: subGroup,
            group: true
        });
    };
    ProfilePage.prototype.compose = function () {
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_11__mail_compose__["a" /* ComposePage */], {
            item: {
                recipient: this.identity
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
    var ProfilePage_1;
    ProfilePage = ProfilePage_1 = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["n" /* Component */])({
            selector: 'page-profile',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/profile/profile.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n  </ion-navbar>\n</ion-header>\n<ion-content padding>\n  <ion-row>\n    <ion-col text-center>\n      <ion-item>\n        <h1>{{identity.username}}</h1></ion-item>\n    </ion-col>\n    <ion-col>\n      <button ion-button large secondary (click)="addFriend()" *ngIf="isAdded === false && group !== true">\n        Add contact&nbsp;<ion-icon name="create"></ion-icon>\n      </button>\n      <button ion-button large secondary (click)="createSubGroup()" *ngIf="isAdded === true && group === true">\n        Create sub-group&nbsp;<ion-icon name="create"></ion-icon>\n      </button>\n      <button ion-button large secondary (click)="compose()" *ngIf="isAdded === true">\n        Compose message&nbsp;<ion-icon name="create"></ion-icon>\n      </button>\n      <button ion-button large secondary (click)="message()" *ngIf="isAdded === true && !group">\n        Chat&nbsp;<ion-icon name="create"></ion-icon>\n      </button>\n      <button ion-button large secondary (click)="message()" *ngIf="isAdded === true && group === true">\n        Group chat&nbsp;<ion-icon name="create"></ion-icon>\n      </button>\n      <a href="https://centeridentity.com/skynet/skylink/{{identity.skylink}}" *ngIf="identity.skylink" target="_blank">\n        <button ion-button large secondary>\n          Download&nbsp;<ion-icon name="create"></ion-icon>\n        </button>\n      </a>\n    </ion-col>\n  </ion-row>\n  <ion-row>\n    <h4>Manage access</h4>\n    <ion-list>\n      <ion-item>\n\n      </ion-item>\n    </ion-list>\n  </ion-row>\n  <ion-row *ngIf="settingsService.remoteSettings.restricted">\n    <h4>Public identity <ion-spinner *ngIf="busy"></ion-spinner></h4>\n    <ion-item>\n      <ion-textarea type="text" [(ngModel)]="identitySkylink" autoGrow="true" rows="1"></ion-textarea>\n    </ion-item>\n  </ion-row>\n  <ion-row *ngIf="!settingsService.remoteSettings.restricted">\n    <h4>Public identity</h4>\n    <ion-item>\n      <ion-textarea type="text" [value]="identityJson" autoGrow="true" rows="5"></ion-textarea>\n    </ion-item>\n  </ion-row>\n  <ion-row>\n    <ion-list>\n      <ng-container *ngFor="let group of graphService.graph.groups">\n        <ion-item *ngIf="group.relationship.parent && group.relationship.parent.username_signature === item.relationship.username_signature" (click)="openSubGroup(group)">\n            {{group.relationship.username}}\n        </ion-item>\n      </ng-container>\n    </ion-list>\n  </ion-row>\n</ion-content>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/profile/profile.html"*/
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["i" /* NavController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["j" /* NavParams */],
            __WEBPACK_IMPORTED_MODULE_2__ionic_storage__["b" /* Storage */],
            __WEBPACK_IMPORTED_MODULE_5__app_wallet_service__["a" /* WalletService */],
            __WEBPACK_IMPORTED_MODULE_3__app_graph_service__["a" /* GraphService */],
            __WEBPACK_IMPORTED_MODULE_4__app_bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_9__angular_http__["b" /* Http */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["f" /* LoadingController */],
            __WEBPACK_IMPORTED_MODULE_10__app_settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["a" /* AlertController */],
            __WEBPACK_IMPORTED_MODULE_6__app_transaction_service__["a" /* TransactionService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["l" /* ToastController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["b" /* Events */]])
    ], ProfilePage);
    return ProfilePage;
}());

//# sourceMappingURL=profile.js.map

/***/ }),

/***/ 666:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return PostModal; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(9);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__app_wallet_service__ = __webpack_require__(24);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_transaction_service__ = __webpack_require__(29);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_opengraphparser_service__ = __webpack_require__(135);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_settings_service__ = __webpack_require__(22);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__angular_http__ = __webpack_require__(21);
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
                            reject('failed to generate transaction');
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
                            reject('failed to generate transaction');
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

/***/ 667:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return GroupPage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(9);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__ionic_storage__ = __webpack_require__(42);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_graph_service__ = __webpack_require__(26);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_bulletinSecret_service__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_wallet_service__ = __webpack_require__(24);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_transaction_service__ = __webpack_require__(29);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__app_settings_service__ = __webpack_require__(22);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__list_list__ = __webpack_require__(61);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__profile_profile__ = __webpack_require__(62);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_10__siafiles_siafiles__ = __webpack_require__(226);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_11__angular_http__ = __webpack_require__(21);
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
        this.public_key = navParams.data.item.transaction.relationship.identity.public_key;
        this.username_signature = navParams.data.item.transaction.relationship.identity.username_signature;
        this.username = navParams.data.item.transaction.relationship.identity.username;
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
        var alert = this.alertCtrl.create();
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
                                public_key: _this.item.public_key,
                                username_signature: _this.item.relationship.identity.username_signature,
                                username: _this.item.relationship.identity.username,
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
        for (var i = 0; i < this.graphService.graph.friends.length; i++) {
            var friend = this.graphService.graph.friends[i];
            alert.addInput({
                name: 'username',
                type: 'radio',
                label: friend.relationship.identity.username,
                value: friend,
                checked: false
            });
        }
        alert.present();
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
        this.graphService.getGroupMessages(this.username_signature, this.requested_rid, this.rid)
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
                username_signature: this.username_signature,
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
        var username_signatures = [this.bulletinSecretService.username_signature, item.relationship.identity.username_signature].sort(function (a, b) {
            return a.toLowerCase().localeCompare(b.toLowerCase());
        });
        if (username_signatures[0] === username_signatures[1])
            return;
        var rid = foobar.bitcoin.crypto.sha256(username_signatures[0] + username_signatures[1]).toString('hex');
        for (var i = 0; i < this.graphService.graph.friends.length; i++) {
            var friend = this.graphService.graph.friends[i];
            if (friend.rid === rid) {
                item = friend;
            }
        }
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_9__profile_profile__["a" /* ProfilePage */], {
            item: item
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
                    return _this.transactionService.generateTransaction({
                        relationship: {
                            groupChatText: _this.groupChatText,
                            username_signature: _this.bulletinSecretService.generate_username_signature(),
                            username: _this.bulletinSecretService.username
                        },
                        username_signature: _this.username_signature,
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
                            username_signature: _this.bulletinSecretService.username_signature,
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
            selector: 'page-group',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/group/group.html"*/'<ion-header>\n    <ion-navbar>\n      <button ion-button menuToggle color="{{color}}">\n        <ion-icon name="menu"></ion-icon>\n      </button>\n      <button ion-button color="{{chatColor}}" title="Create invite" (click)="showInvite()">\n        Invite&nbsp;<ion-icon name="contacts"></ion-icon>\n      </button>\n    </ion-navbar>\n  </ion-header>\n  <ion-content #content>\n    <ion-refresher (ionRefresh)="refresh($event)">\n      <ion-refresher-content></ion-refresher-content>\n    </ion-refresher>\n    <ion-spinner *ngIf="loading"></ion-spinner>\n      <ion-list>\n        <ion-item *ngFor="let item of chats" text-wrap (click)="toggleExtraInfo(item.pending)">\n          <strong><span ion-text style="font-size: 20px;" (click)="viewProfile(item)">{{item.relationship.identity.username || \'Anonymous\'}}</span> </strong><span style="font-size: 10px; color: rgb(88, 88, 88);" ion-text>{{item.time}}</span>\n          <h3 *ngIf="!item.relationship.groupChatFileName">{{item.relationship.groupChatText}}</h3>\n          <h3 *ngIf="item.relationship.groupChatFileName" (click)="receive(item.relationship)">{{item.relationship.groupChatFileName}}</h3>\n          <button *ngIf="item.relationship.groupChatFileName" ion-button (click)="import(item.relationship)">Import</button>\n          <ion-note color="primary">{{item.fee}} YADA</ion-note>\n          <ion-note *ngIf="item.pending" color="danger">Pending</ion-note>\n          <ion-note *ngIf="!item.pending" color="secondary">Saved</ion-note>\n          <hr />\n        </ion-item>\n      </ion-list>\n  </ion-content>\n  <ion-footer>\n    <ion-item>\n      <ion-label floating>Group text</ion-label>\n      <ion-input [(ngModel)]="groupChatText" (keyup.enter)="send()"></ion-input>\n    </ion-item>\n    <button ion-button (click)="send()">Send</button>\n    <button ion-button (click)="presentModal()">Share file</button>\n  </ion-footer>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/group/group.html"*/,
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

/***/ })

},[407]);
//# sourceMappingURL=main.js.map