webpackJsonp([0],{

/***/ 10:
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
        this.collections = {
            AFFILIATE: 'affiliate',
            ASSET: 'asset',
            BID: 'bid',
            CONTACT: 'contact',
            CALENDAR: 'event_meeting',
            CHAT: 'chat',
            CHAT_FILE: 'chat_file',
            CONTRACT: 'contract',
            CONTRACT_SIGNED: 'contract_signed',
            GROUP: 'group',
            GROUP_CALENDAR: 'group_event_meeting',
            GROUP_CHAT: 'group_chat',
            GROUP_CHAT_FILE_NAME: 'group_chat_file_name',
            GROUP_CHAT_FILE: 'group_chat_file',
            GROUP_MAIL: 'group_mail',
            MAIL: 'mail',
            MARKET: 'market',
            PERMISSION_REQUEST: 'permission_request',
            SIGNATURE_REQUEST: 'signature_request',
            SMART_CONTRACT: 'smart_contract',
            WEB_CHALLENGE_REQUEST: 'web_challenge_request',
            WEB_CHALLENGE_RESPONSE: 'web_challenge_response',
            WEB_PAGE: 'web_page',
            WEB_PAGE_REQUEST: 'web_page_request',
            WEB_PAGE_RESPONSE: 'web_page_response',
            WEB_SIGNIN_REQUEST: 'web_signin_request',
            WEB_SIGNIN_RESPONSE: 'web_signin_response'
        };
        this.tokens = {};
        this.latest_block = {};
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

/***/ 109:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return ComposePage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(5);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__app_autocomplete_provider__ = __webpack_require__(110);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__angular_forms__ = __webpack_require__(30);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4_ionic2_auto_complete__ = __webpack_require__(391);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_graph_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_transaction_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__app_wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__app_bulletinSecret_service__ = __webpack_require__(14);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__angular_http__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_10__app_settings_service__ = __webpack_require__(10);
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
            this.collection = this.item.collection;
        }
        else if (this.mode === 'replyToAll') {
            this.recipient = this.item.group;
            this.subject = this.item.subject;
            this.prevBody = this.item.body;
            this.collection = this.item.collection;
        }
        else if (this.mode === 'forward') {
            this.subject = this.item.subject;
            this.body = this.item.body;
            this.collection = this.item.collection;
        }
        else if (this.item && this.item.recipient) {
            this.recipient = this.item.recipient;
        }
        if (this.recipient) {
            this.collection = this.graphService.isGroup(this.recipient) ? this.settingsService.collections.GROUP_MAIL : this.settingsService.collections.MAIL;
        }
        if (this.item && this.item.message_type) {
            this.message_type = this.item.message_type;
        }
        else {
            if (this.collection === this.settingsService.collections.MAIL || this.collection === this.settingsService.collections.GROUP_MAIL) {
                this.message_type = 'mail';
            }
            else if (this.collection === this.settingsService.collections.CALENDAR || this.collection === this.settingsService.collections.GROUP_CALENDAR) {
                this.message_type = 'calendar';
            }
            this.message_type = this.message_type || 'mail';
        }
    };
    ComposePage.prototype.segmentChanged = function (e) {
        this.message_type = e.value;
        if (this.message_type === 'mail') {
            this.collection = this.graphService.isGroup(this.recipient) ? this.settingsService.collections.GROUP_MAIL : this.settingsService.collections.MAIL;
        }
        else if (this.message_type === 'calendar') {
            this.collection = this.graphService.isGroup(this.recipient) ? this.settingsService.collections.GROUP_CALENDAR : this.settingsService.collections.CALENDAR;
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
        if (this.message_type === 'mail') {
            this.collection = this.graphService.isGroup(this.recipient) ? this.settingsService.collections.GROUP_MAIL : this.settingsService.collections.MAIL;
        }
        else if (this.message_type === 'calendar') {
            this.collection = this.graphService.isGroup(this.recipient) ? this.settingsService.collections.GROUP_CALENDAR : this.settingsService.collections.CALENDAR;
        }
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
                    if (_this.graphService.isGroup(_this.recipient)) {
                        var requester_rid = _this.graphService.generateRid(_this.bulletinSecretService.identity.username_signature, _this.bulletinSecretService.identity.username_signature, _this.collection);
                        var requested_rid = _this.graphService.generateRid(_this.recipient.username_signature, _this.recipient.username_signature, _this.collection);
                        var info = {
                            relationship: {},
                            rid: rid,
                            requester_rid: requester_rid,
                            requested_rid: requested_rid,
                            group: true,
                            shared_secret: _this.recipient.username_signature
                        };
                        info.relationship[_this.collection] = {
                            sender: _this.bulletinSecretService.identity,
                            subject: _this.subject,
                            body: _this.body,
                            thread: _this.thread,
                            event_datetime: _this.event_datetime,
                            skylink: _this.skylink,
                            filename: _this.filepath
                        };
                        return _this.transactionService.generateTransaction(info);
                    }
                    else {
                        var requester_rid = _this.graphService.generateRid(_this.bulletinSecretService.identity.username_signature, _this.bulletinSecretService.identity.username_signature, _this.collection);
                        var requested_rid = _this.graphService.generateRid(_this.recipient.username_signature, _this.recipient.username_signature, _this.collection);
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
                            var info = {
                                dh_public_key: dh_public_key,
                                dh_private_key: dh_private_key,
                                relationship: {},
                                shared_secret: shared_secret,
                                rid: rid,
                                requester_rid: requester_rid,
                                requested_rid: requested_rid
                            };
                            info.relationship[_this.collection] = {
                                subject: _this.subject,
                                body: _this.body,
                                thread: _this.thread,
                                event_datetime: _this.event_datetime,
                                skylink: _this.skylink,
                                filename: _this.filepath
                            };
                            return _this.transactionService.generateTransaction(info);
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
            selector: 'compose-profile',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/mail/compose.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n  </ion-navbar>\n</ion-header>\n<ion-content padding>\n  What type of message is this?\n  <ion-segment (ionChange)="segmentChanged($event)" [(ngModel)]="message_type" value="mail">\n    <ion-segment-button value="mail">\n      {{graphService.isGroup(recipient) ? \'Group \': \'\'}}Mail\n    </ion-segment-button>\n    <ion-segment-button value="calendar">\n      {{graphService.isGroup(recipient) ? \'Group \': \'\'}}Event / Meeting\n    </ion-segment-button>\n  </ion-segment>\n  <button ion-button secondary (click)="submit()" [disabled]="busy || !recipient || (message_type === \'calendar\' && !event_datetime)">Send \n    <ion-spinner *ngIf="busy"></ion-spinner>\n  </button>\n  <form [formGroup]="myForm" (ngSubmit)="submit()" *ngIf="!recipient">\n    <ion-auto-complete #searchbar [(ngModel)]="recipient" [options]="{ placeholder : \'Recipient\' }" [dataProvider]="completeTestService" formControlName="searchTerm" required></ion-auto-complete>\n  </form>\n  <ion-item *ngIf="recipient" title="Verified" class="sender">{{recipient.username}} <ion-icon *ngIf="graphService.isAdded(recipient)" name="checkmark-circle" class="success"></ion-icon></ion-item>\n  <ion-item *ngIf="message_type === \'calendar\'">\n    <ion-label floating>Date &amp; time</ion-label>\n    <ion-datetime displayFormat="D MMM YYYY H:mm" [(ngModel)]="event_datetime"></ion-datetime>\n  </ion-item>\n  <ion-item>\n    <ion-label floating>Subject</ion-label>\n    <ion-input type="text" [(ngModel)]="subject"></ion-input>\n  </ion-item>\n  <ion-item>\n    <ion-label floating>Body</ion-label>\n    <ion-textarea type="text" [(ngModel)]="body" rows="5" autoGrow="true"></ion-textarea>\n  </ion-item>\n  <ion-item *ngIf="settingsService.remoteSettings.restricted">\n    <ion-label id="profile_image" color="primary"></ion-label>\n    <ion-input type="file" (change)="changeListener($event)"></ion-input>\n  </ion-item>\n  <br>\n  <ion-item *ngIf="item && item.sender">\n    Previous message\n    <div title="Verified" class="sender">\n      <span>{{item.sender.username}} <ion-icon *ngIf="graphService.isAdded(item.sender)" name="checkmark-circle" class="success"></ion-icon></span>\n      <span *ngIf="item.group">{{item.group.username}} <ion-icon *ngIf="graphService.isAdded(item.group)" name="checkmark-circle" class="success"></ion-icon></span>\n    </div>\n    <div class="subject">{{item.subject}}</div>\n    <div class="datetime">{{item.datetime}}</div>\n    <div class="body">{{item.body}}</div>\n  </ion-item>\n</ion-content>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/mail/compose.html"*/
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

/***/ 110:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return CompleteTestService; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__settings_service__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__bulletinSecret_service__ = __webpack_require__(14);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__angular_http__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4_rxjs_add_operator_map__ = __webpack_require__(673);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4_rxjs_add_operator_map___default = __webpack_require__.n(__WEBPACK_IMPORTED_MODULE_4_rxjs_add_operator_map__);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__graph_service__ = __webpack_require__(16);
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
        var _this = this;
        return this.graphService.graph.friends.concat(this.graphService.graph.groups)
            .filter(function (item) {
            var friend = _this.graphService.getIdentityFromTxn(item, _this.settingsService.collections.CONTACT);
            var group = _this.graphService.getIdentityFromTxn(item, _this.settingsService.collections.GROUP);
            return (friend || group).username.toLowerCase().indexOf(searchTerm.toLowerCase()) > -1;
        })
            .map(function (item) {
            var friend = _this.graphService.getIdentityFromTxn(item, _this.settingsService.collections.CONTACT);
            var group = _this.graphService.getIdentityFromTxn(item, _this.settingsService.collections.GROUP);
            var identity = friend || group;
            return { name: identity.username, value: _this.graphService.toIdentity(identity) };
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

/***/ 138:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return MailItemPage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(5);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__app_bulletinSecret_service__ = __webpack_require__(14);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_graph_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_transaction_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__compose__ = __webpack_require__(109);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__profile_profile__ = __webpack_require__(70);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__app_settings_service__ = __webpack_require__(10);
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
    function MailItemPage(navCtrl, navParams, walletService, graphService, bulletinSecretService, alertCtrl, transactionService, settingsService) {
        this.navCtrl = navCtrl;
        this.navParams = navParams;
        this.walletService = walletService;
        this.graphService = graphService;
        this.bulletinSecretService = bulletinSecretService;
        this.alertCtrl = alertCtrl;
        this.transactionService = transactionService;
        this.settingsService = settingsService;
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
            selector: 'mail-item',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/mail/mailitem.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n    <ion-title>{{item.subject}}</ion-title>\n  </ion-navbar>\n</ion-header>\n<ion-content padding>\n  <button ion-button secondary (click)="replyMail(item)" *ngIf="graphService.isAdded(item.sender)">Reply</button>\n  <button ion-button secondary (click)="addFriend(item)" *ngIf="!graphService.isAdded(item.sender) && !graphService.isMe(item.sender)">Add sender as contact</button>\n  <button *ngIf="item.group" ion-button secondary (click)="replyToAllMail(item)">Reply to all</button>\n  <button ion-button secondary (click)="forwardMail(item)">Forward</button>\n  <button *ngIf="item.message_type == settingsService.collections.CONTRACT" ion-button secondary (click)="signMail(item)">Sign</button>\n  <div title="Verified" class="sender">\n    <span (click)="viewProfile(item.sender)">{{item.sender.username}} <ion-icon *ngIf="graphService.isAdded(item.sender)" name="checkmark-circle" class="success"></ion-icon></span>\n    <span *ngIf="item.group" (click)="viewProfile(item.group)">{{item.group.username}} <ion-icon *ngIf="graphService.isAdded(item.group)" name="checkmark-circle" class="success"></ion-icon></span>\n  </div>\n  <div *ngIf="item.message_type == settingsService.collections.CONTRACT_SIGNED"><strong>Contract signed</strong> <ion-icon name="checkmark-circle" class="success"></ion-icon></div>\n  <ion-item>{{item.datetime}}</ion-item>\n  <ion-item *ngIf="item.event_datetime">{{item.event_datetime}}</ion-item>\n  <ion-item><pre>{{item.body}}</pre></ion-item>\n  <ion-item *ngIf="item.skylink"><a href="https://centeridentity.com/sia-download?skylink={{item.skylink}}" target="_blank">Download {{item.filename}}</a></ion-item>\n</ion-content>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/mail/mailitem.html"*/
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["i" /* NavController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["j" /* NavParams */],
            __WEBPACK_IMPORTED_MODULE_5__app_wallet_service__["a" /* WalletService */],
            __WEBPACK_IMPORTED_MODULE_3__app_graph_service__["a" /* GraphService */],
            __WEBPACK_IMPORTED_MODULE_2__app_bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["a" /* AlertController */],
            __WEBPACK_IMPORTED_MODULE_4__app_transaction_service__["a" /* TransactionService */],
            __WEBPACK_IMPORTED_MODULE_8__app_settings_service__["a" /* SettingsService */]])
    ], MailItemPage);
    return MailItemPage;
}());

//# sourceMappingURL=mailitem.js.map

/***/ }),

/***/ 139:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return MarketItemPage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(5);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__app_bulletinSecret_service__ = __webpack_require__(14);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_graph_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_transaction_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__profile_profile__ = __webpack_require__(70);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__app_settings_service__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__app_smartContract_service__ = __webpack_require__(68);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__app_websocket_service__ = __webpack_require__(37);
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











var MarketItemPage = /** @class */ (function () {
    function MarketItemPage(navCtrl, navParams, walletService, graphService, bulletinSecretService, alertCtrl, transactionService, settingsService, smartContractService, websocketService, ahttp) {
        var _this = this;
        this.navCtrl = navCtrl;
        this.navParams = navParams;
        this.walletService = walletService;
        this.graphService = graphService;
        this.bulletinSecretService = bulletinSecretService;
        this.alertCtrl = alertCtrl;
        this.transactionService = transactionService;
        this.settingsService = settingsService;
        this.smartContractService = smartContractService;
        this.websocketService = websocketService;
        this.ahttp = ahttp;
        this.item = navParams.get('item');
        this.smartContract = this.item.relationship[this.settingsService.collections.SMART_CONTRACT];
        this.market = navParams.get('market').relationship[this.settingsService.collections.MARKET];
        this.bids = [];
        this.affiliates = [];
        this.sentPage = 1;
        this.past_sent_page_cache = {};
        this.past_sent_transactions = [];
        this.refresh();
        this.price = this.smartContract.price;
        this.minPrice = this.smartContract.price;
        this.graphService.getBlockHeight()
            .then(function (data) {
            _this.settingsService.latest_block = data;
        });
        this.prevHeight = this.settingsService.latest_block.height;
        setInterval(function () {
            if (_this.prevHeight < _this.settingsService.latest_block.height) {
                _this.prevHeight = _this.settingsService.latest_block.height;
                _this.graphService.getSmartContracts(_this.market)
                    .then(function (smartContracts) {
                    var item = smartContracts.filter(function (item) {
                        return item.id === _this.item.id;
                    })[0];
                    _this.item = item || _this.item;
                });
                _this.refresh();
            }
        }, 1000);
    }
    MarketItemPage.prototype.refresh = function (e) {
        var _this = this;
        if (e === void 0) { e = null; }
        var identity = JSON.parse(JSON.stringify(this.smartContract.identity));
        if (this.smartContract.contract_type === this.smartContractService.contractTypes.CHANGE_OWNERSHIP) {
            identity.collection = this.settingsService.collections.BID;
        }
        else {
            identity.collection = this.settingsService.collections.AFFILIATE;
        }
        var rids = this.graphService.generateRids(identity);
        var scAddress = this.bulletinSecretService.publicKeyToAddress(this.smartContract.identity.public_key);
        this.walletService.get(this.price, scAddress)
            .then(function (wallet) {
            _this.balance = _this.item.pending ? wallet.pending_balance : wallet.balance;
            return _this.graphService.getBids(rids.requested_rid, _this.market);
        })
            .then(function (bids) {
            _this.bids = bids.sort(function (a, b) {
                var aamount = _this.getAmount(a);
                var bamount = _this.getAmount(b);
                if (aamount < bamount)
                    return 1;
                if (aamount > bamount)
                    return -1;
                if (aamount === bamount)
                    return 0;
            });
            if (_this.bids.slice(0).length > 0) {
                _this.price = _this.getAmount(_this.bids[0]);
                _this.minPrice = _this.price;
            }
        });
        this.graphService.getAffiliates(rids.requested_rid, this.market)
            .then(function (affiliates) {
            _this.affiliates = affiliates.filter(function (item) {
                if (item.public_key === _this.bulletinSecretService.identity.public_key ||
                    _this.item.public_key === _this.bulletinSecretService.identity.public_key)
                    return true;
            });
        });
        this.smartContractAddress = foobar.bitcoin.ECPair.fromPublicKeyBuffer(foobar.Buffer.Buffer.from(this.smartContract.identity.public_key, 'hex')).getAddress();
        this.getSentHistory();
        setTimeout(function () {
            e && e.complete();
        }, 1000);
    };
    MarketItemPage.prototype.getSentHistory = function (public_key) {
        var _this = this;
        if (public_key === void 0) { public_key = null; }
        return new Promise(function (resolve, reject) {
            var options = new __WEBPACK_IMPORTED_MODULE_10__angular_http__["d" /* RequestOptions */]({ withCredentials: true });
            _this.ahttp.get(_this.settingsService.remoteSettings['baseUrl'] + '/get-past-sent-txns?page=' + _this.sentPage + '&public_key=' + _this.smartContract.identity.public_key + '&origin=' + encodeURIComponent(window.location.origin), options)
                .subscribe(function (res) {
                _this.past_sent_transactions = res.json()['past_transactions'].sort(_this.sortFunc);
                _this.past_sent_transactions = _this.breakApartByOutput();
                _this.getSentOutputValue(_this.past_sent_transactions);
                _this.past_sent_page_cache[_this.sentPage] = _this.past_sent_transactions;
                resolve(res);
            }, function (err) {
                return reject('cannot unlock wallet');
            });
        });
    };
    MarketItemPage.prototype.breakApartByOutput = function () {
        var _this = this;
        var new_array = [];
        this.past_sent_transactions.map(function (item) {
            item.outputs.map(function (output) {
                if (_this.smartContractAddress === output.to)
                    return;
                var new_item = JSON.parse(JSON.stringify(item));
                new_item.outputs = [output];
                new_array.push(new_item);
            });
        });
        return new_array;
    };
    MarketItemPage.prototype.prevSentPage = function () {
        this.sentPage--;
        var result = this.past_sent_transactions = this.past_sent_page_cache[this.sentPage] || [];
        if (result.length > 0) {
            this.past_sent_transactions = result;
            return;
        }
        return this.getSentHistory();
    };
    MarketItemPage.prototype.nextSentPage = function () {
        this.sentPage++;
        var result = this.past_sent_page_cache[this.sentPage] || [];
        if (result.length > 0) {
            this.past_sent_transactions = result;
            return;
        }
        return this.getSentHistory();
    };
    MarketItemPage.prototype.getSentOutputValue = function (array) {
        for (var i = 0; i < array.length; i++) {
            var txn = array[i];
            if (!array[i]['value']) {
                array[i]['value'] = 0;
            }
            for (var j = 0; j < txn['outputs'].length; j++) {
                var output = txn['outputs'][j];
                if (this.smartContractAddress !== output.to) {
                    array[i]['value'] += parseFloat(output.value);
                    if (output.to)
                        array[i]['to'] = output.to;
                }
                else {
                    if (output.to)
                        array[i]['from'] = output.to;
                }
            }
            array[i]['value'] = array[i]['value'].toFixed(8);
        }
    };
    MarketItemPage.prototype.sortFunc = function (a, b) {
        if (parseInt(a.time) < parseInt(b.time))
            return 1;
        if (parseInt(a.time) > parseInt(b.time))
            return -1;
        return 0;
    };
    MarketItemPage.prototype.convertDateTime = function (timestamp) {
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
    MarketItemPage.prototype.getAmount = function (bid) {
        var total = 0;
        for (var i = 0; i < bid.outputs.length; i++) {
            if (bid.outputs[i].to === this.smartContractAddress)
                total += bid.outputs[i].value;
        }
        return total.toFixed(8);
    };
    MarketItemPage.prototype.openProfile = function (identity) {
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_6__profile_profile__["a" /* ProfilePage */], {
            identity: identity
        });
    };
    MarketItemPage.prototype.buy = function (e) {
        var _this = this;
        // generate purchase txn
        var alert = this.alertCtrl.create();
        var buttonText = '';
        if (this.smartContract.proof_type === this.smartContractService.assetProofTypes.FIRST_COME) {
            alert.setTitle('Buy Asset');
            alert.setSubTitle('Are you sure you want to buy this asset?');
            buttonText = 'Buy';
        }
        else if (this.smartContract.proof_type === this.smartContractService.assetProofTypes.AUCTION) {
            alert.setTitle('Bid on Asset');
            alert.setSubTitle('Are you sure you want to place a bid for this asset?');
            buttonText = 'Bid';
        }
        alert.addButton({
            text: 'Cancel'
        });
        alert.addButton({
            text: buttonText,
            handler: function (data) {
                var scAddress = _this.bulletinSecretService.publicKeyToAddress(_this.smartContract.identity.public_key);
                _this.walletService.get(_this.price)
                    .then(function () {
                    var rids = _this.graphService.generateRids(_this.smartContract.identity, _this.smartContract.identity, _this.settingsService.collections.BID);
                    return _this.websocketService.newtxn(_this.graphService.toIdentity(_this.bulletinSecretService.identity), rids, _this.settingsService.collections.BID, _this.market.username_signature, {
                        to: scAddress,
                        value: _this.price
                    });
                })
                    .then(function () {
                    return _this.refresh();
                })
                    .catch(function (err) {
                    var alert = _this.alertCtrl.create();
                    alert.setTitle('Transaction failed');
                    alert.setSubTitle(err);
                    alert.addButton({
                        text: 'Ok'
                    });
                    alert.present();
                });
            }
        });
        alert.present();
    };
    MarketItemPage.prototype.joinPromotion = function (e) {
        var _this = this;
        // generate purchase txn
        var alert = this.alertCtrl.create();
        var buttonText = '';
        alert.setTitle('Join promotion');
        alert.setSubTitle('Are you sure you want to join this promotion?');
        buttonText = 'Join';
        alert.addButton({
            text: 'Cancel'
        });
        alert.addButton({
            text: buttonText,
            handler: function (data) {
                var rids = _this.graphService.generateRids(_this.smartContract.identity, _this.smartContract.identity, _this.settingsService.collections.AFFILIATE);
                var rid = _this.graphService.generateRid(_this.smartContract.identity.username_signature, _this.bulletinSecretService.username_signature);
                rids.rid = rid;
                _this.websocketService.newtxn({
                    referrer: _this.graphService.toIdentity(_this.bulletinSecretService.identity),
                    target: _this.smartContract.target,
                    contract: _this.graphService.toIdentity(_this.smartContract.identity)
                }, rids, _this.settingsService.collections.AFFILIATE, _this.market.username_signature)
                    .then(function () {
                    return _this.refresh();
                })
                    .catch(function (err) {
                    var alert = _this.alertCtrl.create();
                    alert.setTitle('Transaction failed');
                    alert.setSubTitle(err);
                    alert.addButton({
                        text: 'Ok'
                    });
                    alert.present();
                });
            }
        });
        alert.present();
    };
    MarketItemPage.prototype.toHex = function (byteArray) {
        var callback = function (byte) {
            return ('0' + (byte & 0xFF).toString(16)).slice(-2);
        };
        return Array.from(byteArray, callback).join('');
    };
    MarketItemPage = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["n" /* Component */])({
            selector: 'market-item',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/markets/marketitem.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n  </ion-navbar>\n</ion-header>\n\n<ion-content padding>\n  <ion-refresher (ionRefresh)="refresh($event)">\n    <ion-refresher-content></ion-refresher-content>\n  </ion-refresher>\n  <ion-row *ngIf="smartContract.contract_type === smartContractService.contractTypes.CHANGE_OWNERSHIP">\n    <ion-col col-md-3>\n      <h1 *ngIf="smartContract.proof_type === \'first_come\'">Asset for sale</h1>\n      <h1 *ngIf="smartContract.proof_type === \'auction\'">Asset auction</h1>\n      <h3>Info</h3>\n      <ion-card ion-item style="">\n        <ion-card-title style="text-overflow:ellipsis;" text-wrap>\n          <img [src]="smartContract.asset.data">\n        </ion-card-title>\n        <ion-card-content>\n          <strong>Name: </strong>{{smartContract.asset.identity.username}}\n        </ion-card-content>\n        <ion-card-content>\n          <strong>Type: </strong>{{smartContract.proof_type}}\n        </ion-card-content>\n        <ion-card-content *ngIf="smartContract.proof_type === \'auction\'">\n          <strong>Reserve: </strong>{{smartContract.price.toFixed(8)}} YDA\n        </ion-card-content>\n        <ion-card-content *ngIf="smartContract.proof_type === \'first_come\'">\n          <strong>Price: </strong>{{smartContract.price.toFixed(8)}} YDA\n        </ion-card-content>\n        <ion-card-content *ngIf="smartContract.proof_type === \'first_come\'">\n          <strong>Seller: </strong><span *ngIf="smartContract.creator" (click)="openProfile(smartContract.creator)">{{smartContract.creator.username}} <ion-icon *ngIf="graphService.isAdded(smartContract.creator)" name="checkmark-circle" class="success"></ion-icon></span>\n        </ion-card-content>\n        <ion-card-content *ngIf="(smartContract.expiry - settingsService.latest_block.height) >= 0">\n          <strong>Expires: </strong>In {{smartContract.expiry - settingsService.latest_block.height}} blocks\n        </ion-card-content>\n        <ion-card-content *ngIf="(smartContract.expiry - settingsService.latest_block.height) < 0">\n          <strong>Expired: </strong>{{settingsService.latest_block.height - smartContract.expiry}} blocks ago\n        </ion-card-content>\n      </ion-card>\n      <ion-item *ngIf="smartContract.proof_type === \'auction\'">\n        <ion-label color="primary">Bid amount</ion-label>\n        <ion-input type="number" [min]="minPrice" [(ngModel)]="price" placeholder="How much YDA are you bidding?" [disabled]="item.pending"></ion-input>\n      </ion-item>\n      <button ion-button secondary *ngIf="!item.pending && smartContract.proof_type === \'auction\'" (click)="buy($event)" [disabled]="price < minPrice || (smartContract.expiry - settingsService.latest_block.height) < 0">Place bid</button>\n      <button ion-button secondary *ngIf="item.pending" (click)="buy($event)" [disabled]="item.pending">Pending blockchain insertion</button>\n      <button ion-button secondary *ngIf="!item.pending && bids.length === 0 && smartContract.proof_type === \'first_come\'" (click)="buy($event)" [disabled]="price < minPrice || (smartContract.expiry - settingsService.latest_block.height) < 0">Buy this asset</button>\n      <button ion-button secondary *ngIf="!item.pending && bids.length > 0 && smartContract.proof_type === \'first_come\'" disabled=disabled>This item is sold</button>\n    </ion-col>\n    <ion-col col-md-3 *ngIf="smartContract.proof_type === \'auction\'">\n      <h3>Bids</h3>\n      <ion-list>\n        <ion-item *ngIf="bids.length === 0">No bids yet</ion-item>\n        <ion-item *ngFor="let bid of bids" (click)="openProfile(bid.relationship[settingsService.collections.BID])">\n          {{bid.relationship[settingsService.collections.BID].username}}\n          <ion-icon\n            *ngIf="graphService.isAdded(bid.relationship[settingsService.collections.BID])"\n            name="checkmark-circle"\n            class="success"\n          >\n          </ion-icon> {{getAmount(bid)}} YDA</ion-item>\n      </ion-list>\n    </ion-col>\n  </ion-row>\n  <ion-row *ngIf="smartContract.contract_type === smartContractService.contractTypes.NEW_RELATIONSHIP">\n    <ion-col col-md-3>\n      <h1>Referrals</h1>\n      <h3>Info</h3>\n      <ion-card ion-item>\n        <ion-card-content>\n          <strong>Name: </strong>{{smartContract.target.username}}\n        </ion-card-content>\n        <ion-card-content>\n          <strong>Type: </strong>{{smartContract.proof_type}}\n        </ion-card-content>\n      </ion-card>\n      <ng-container *ngIf="smartContract.referrer.active">\n        <h3>Referrer payout</h3>\n        <ion-item>\n          Operator: {{smartContract.referrer.operator}}\n        </ion-item>\n        <ion-item>\n          Payout type: {{smartContract.referrer.payout_type}}\n        </ion-item>\n        <ion-item>\n          Payout interval: Every {{smartContract.referrer.interval}} blocks\n        </ion-item>\n        <ion-item>\n          Amount: {{smartContract.referrer.amount.toFixed(8)}} YDA\n        </ion-item>\n      </ng-container>\n      <ng-container *ngIf="smartContract.referee.active">\n        <h3>Referee payout</h3>\n        <ion-item>\n          Operator: {{smartContract.referee.operator}}\n        </ion-item>\n        <ion-item>\n          Payout type: {{smartContract.referee.payout_type}}\n        </ion-item>\n        <ion-item>\n          Payout interval: Every {{smartContract.referee.interval}} blocks\n        </ion-item>\n        <ion-item>\n          Amount: {{smartContract.referee.amount.toFixed(8)}} YDA\n        </ion-item>\n      </ng-container>\n      <h3>Funding</h3>\n      <ion-item>\n        Balance: {{balance}} YDA\n      </ion-item>\n      <ion-item *ngIf="(smartContract.expiry - settingsService.latest_block.height) >= 0">\n        Expires: In {{smartContract.expiry - settingsService.latest_block.height}} blocks\n      </ion-item>\n      <ion-item *ngIf="(smartContract.expiry - settingsService.latest_block.height) < 0">\n        Expired: {{settingsService.latest_block.height - smartContract.expiry}} blocks ago\n      </ion-item>\n    </ion-col>\n    <ion-col col-md-3>\n      <h1>&nbsp;</h1>\n      <h3>Affiliate code</h3>\n      <ion-list>\n        <ion-item *ngIf="item.public_key === bulletinSecretService.identity.public_key && affiliates.length === 0">No affiliates have joined your program yet</ion-item>\n        <ion-item *ngIf="item.public_key !== bulletinSecretService.identity.public_key && affiliates.length === 0">You have not joined the promotion yet</ion-item>\n        <ion-item\n          *ngFor="let affiliate of affiliates"\n        >\n          <ion-label color="primary"></ion-label>\n          <ion-input type="text" [value]="affiliate.pending ? \'Promo code pending blockchain insertion\' : affiliate.rid"></ion-input>\n        </ion-item>\n      </ion-list>\n      <button ion-button secondary  (click)="joinPromotion($event)" [disabled]="item.pending || (affiliates.length && affiliates.length > 0)">{{item.pending ? \'Pending block insertion\' : \'Become an Affiliate\'}}</button>\n    </ion-col>\n  </ion-row>\n  <ion-row>\n    <ion-col>\n      <h4>Transaction history</h4>\n      <strong>Sent</strong><br>\n      <button ion-button small (click)="prevSentPage()" [disabled]="sentPage <= 1">< Prev</button> <button ion-button small (click)="nextSentPage()" [disabled]="past_sent_transactions.length === 0 || past_sent_transactions.length < 10">Next ></button>\n      <p *ngIf="past_sent_transactions.length === 0">No more results</p><span *ngIf="sentLoading"> (loading...)</span>\n      <ion-list>\n        <ion-item *ngFor="let txn of past_sent_transactions">\n          <ion-label>{{convertDateTime(txn.time)}}</ion-label>\n          <ion-label>{{txn.to}}</ion-label>\n          <ion-label>{{txn.value}}</ion-label>\n        </ion-item>\n      </ion-list>\n    </ion-col>\n  </ion-row>\n</ion-content>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/markets/marketitem.html"*/
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["i" /* NavController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["j" /* NavParams */],
            __WEBPACK_IMPORTED_MODULE_5__app_wallet_service__["a" /* WalletService */],
            __WEBPACK_IMPORTED_MODULE_3__app_graph_service__["a" /* GraphService */],
            __WEBPACK_IMPORTED_MODULE_2__app_bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["a" /* AlertController */],
            __WEBPACK_IMPORTED_MODULE_4__app_transaction_service__["a" /* TransactionService */],
            __WEBPACK_IMPORTED_MODULE_7__app_settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_8__app_smartContract_service__["a" /* SmartContractService */],
            __WEBPACK_IMPORTED_MODULE_9__app_websocket_service__["a" /* WebSocketService */],
            __WEBPACK_IMPORTED_MODULE_10__angular_http__["b" /* Http */]])
    ], MarketItemPage);
    return MarketItemPage;
}());

//# sourceMappingURL=marketitem.js.map

/***/ }),

/***/ 14:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return BulletinSecretService; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__ionic_storage__ = __webpack_require__(48);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2_ionic_angular__ = __webpack_require__(5);
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
    BulletinSecretService.prototype.cloneIdentity = function () {
        return JSON.parse(this.identityJson());
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
        return foobar.bitcoin.ECPair.fromPublicKeyBuffer(foobar.Buffer.Buffer.from(public_key, 'hex')).getAddress();
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

/***/ 140:
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
/* WEBPACK VAR INJECTION */(function(Buffer) {/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return GraphService; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__ionic_storage__ = __webpack_require__(48);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__bulletinSecret_service__ = __webpack_require__(14);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__transaction_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__settings_service__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__ionic_native_badge__ = __webpack_require__(390);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__angular_http__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7_ionic_angular__ = __webpack_require__(5);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8_rxjs_operators__ = __webpack_require__(52);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__ionic_native_geolocation__ = __webpack_require__(224);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_10__wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_11_eciesjs__ = __webpack_require__(353);
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
    function GraphService(storage, bulletinSecretService, settingsService, badge, platform, ahttp, transactionService, geolocation, walletService, events) {
        this.storage = storage;
        this.bulletinSecretService = bulletinSecretService;
        this.settingsService = settingsService;
        this.badge = badge;
        this.platform = platform;
        this.ahttp = ahttp;
        this.transactionService = transactionService;
        this.geolocation = geolocation;
        this.walletService = walletService;
        this.events = events;
        this.graph = {
            messages: [],
            friends: [],
            groups: [],
            files: [],
            mail: [],
            markets: [],
            smart_contracts: [],
            mypages: []
        };
        // online = {};
        // onlineNav = [];
        this.notifications = {};
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
        this.getMyPagesError = false;
        this.usernames = {};
        this.username_signature = '';
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
        this.groups_indexed = {};
        this.counts = {};
    }
    GraphService.prototype.resetGraph = function () {
        this.graph = {
            messages: {},
            friends: [],
            groups: [],
            files: [],
            mail: [],
            markets: [],
            smart_contracts: [],
            mypages: []
        };
        this.groups_indexed = {};
        this.friends_indexed = {};
        this.notifications = {};
        for (var i = 0; i < Object.keys(this.settingsService.collections).length; i++) {
            var collectionKey = Object.keys(this.settingsService.collections)[i];
            if (!this.notifications[this.settingsService.collections[collectionKey]])
                this.notifications[this.settingsService.collections[collectionKey]] = [];
        }
        if (!this.notifications['notifications'])
            this.notifications['notifications'] = [];
    };
    GraphService.prototype.refreshFriendsAndGroups = function () {
        var _this = this;
        this.resetGraph();
        return this.getGroups()
            .then(function (results) {
            return _this.getGroups(null, 'file');
        })
            .then(function (results) {
            return _this.getGroups(null, _this.settingsService.collections.MARKET);
        })
            .then(function (results) {
            var promises = _this.graph.markets.map(function (market) {
                return _this.getGroups(_this.generateRid(market.relationship[_this.settingsService.collections.MARKET].username_signature, market.relationship[_this.settingsService.collections.MARKET].username_signature, _this.settingsService.collections.SMART_CONTRACT), _this.settingsService.collections.SMART_CONTRACT);
            });
            return Promise.all(promises);
        })
            .then(function () {
            return _this.getFriendRequests();
        })
            // .then(() => {
            //   const promises = this.graph.smart_contracts.map((smart_contract) => {
            //     return this.getFriendRequests(
            //       this.generateRid(
            //         smart_contract.relationship[this.settingsService.collections.SMART_CONTRACT].identity.username_signature,
            //         smart_contract.relationship[this.settingsService.collections.SMART_CONTRACT].identity.username_signature,
            //         this.settingsService.collections.SMART_CONTRACT
            //       )
            //     )
            //   });
            //   return Promise.all(promises)
            // })
            .then(function () {
            return _this.getSharedSecrets();
        });
    };
    GraphService.prototype.getMessagesForAllFriendsAndGroups = function () {
        var promises = [];
        for (var i = 0; i < this.graph.friends.length; i++) {
            promises.push(this.getMessages([this.graph.friends[i].rid], this.settingsService.collections.CHAT, false));
        }
        for (var i = 0; i < this.graph.groups.length; i++) {
            var group = this.getIdentityFromTxn(this.graph.groups[i]);
            var rid = this.generateRid(group.username_signature, group.username_signature, this.settingsService.collections.GROUP_CHAT);
            promises.push(this.getMessages([rid], this.settingsService.collections.GROUP_CHAT, false));
        }
        return Promise.all(promises);
    };
    GraphService.prototype.endpointRequest = function (endpoint, ids, rids, post_data, updateLastCollectionTime) {
        var _this = this;
        if (ids === void 0) { ids = null; }
        if (rids === void 0) { rids = null; }
        if (post_data === void 0) { post_data = null; }
        if (updateLastCollectionTime === void 0) { updateLastCollectionTime = false; }
        return new Promise(function (resolve, reject) {
            if (endpoint.substr(0, 1) !== '/') {
                endpoint = '/' + endpoint;
            }
            var headers = new __WEBPACK_IMPORTED_MODULE_6__angular_http__["a" /* Headers */]();
            headers.append('Authorization', 'Bearer ' + _this.settingsService.tokens[_this.bulletinSecretService.keyname]);
            var options = new __WEBPACK_IMPORTED_MODULE_6__angular_http__["d" /* RequestOptions */]({ headers: headers, withCredentials: true });
            var promise = null;
            if (ids) {
                promise = _this.ahttp.post(_this.settingsService.remoteSettings['graphUrl'] + endpoint + '?origin=' + encodeURIComponent(window.location.origin) + '&username_signature=' + encodeURIComponent(_this.bulletinSecretService.username_signature), { ids: ids, update_last_collection_time: updateLastCollectionTime }, options);
            }
            else if (rids) {
                promise = _this.ahttp.post(_this.settingsService.remoteSettings['graphUrl'] + endpoint + '?origin=' + encodeURIComponent(window.location.origin) + '&username_signature=' + encodeURIComponent(_this.bulletinSecretService.username_signature), { rids: rids, update_last_collection_time: updateLastCollectionTime }, options);
            }
            else if (post_data) {
                promise = _this.ahttp.post(_this.settingsService.remoteSettings['graphUrl'] + endpoint + '?origin=' + encodeURIComponent(window.location.origin) + '&username_signature=' + encodeURIComponent(_this.bulletinSecretService.username_signature), post_data, options);
            }
            else {
                promise = _this.ahttp.get(_this.settingsService.remoteSettings['graphUrl'] + endpoint + '?origin=' + encodeURIComponent(window.location.origin) + '&username_signature=' + encodeURIComponent(_this.bulletinSecretService.username_signature), options);
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
                    return resolve(info);
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
                return resolve(data);
            }).catch(function (err) {
                _this.getGraphError = true;
                reject(null);
            });
        });
    };
    GraphService.prototype.getBlockHeight = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            _this.endpointRequest('get-height')
                .then(function (data) {
                return resolve(data);
            });
        });
    };
    GraphService.prototype.addNotification = function (item, collection) {
        if (!this.notifications[collection])
            this.notifications[collection] = [];
        if (Array.isArray(item)) {
            this.notifications[collection] = this.notifications[collection].concat(item);
        }
        else {
            this.notifications[collection].push(item);
        }
        if (!this.notifications['notifications'])
            this.notifications['notifications'] = [];
        if (Array.isArray(item)) {
            this.notifications['notifications'] = this.notifications['notifications'].concat(item);
        }
        else {
            this.notifications['notifications'].push(item);
        }
        this.events.publish('notification');
    };
    GraphService.prototype.getNotifications = function () {
        return this.notifications;
    };
    GraphService.prototype.getSentFriendRequests = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            var rids = [_this.generateRid(_this.bulletinSecretService.identity.username_signature, _this.bulletinSecretService.identity.username_signature)];
            _this.endpointRequest('get-graph-sent-friend-requests', null, rids)
                .then(function (data) {
                _this.graph.sent_friend_requests = _this.parseSentFriendRequests(data.sent_friend_requests);
                _this.getSentFriendRequestsError = false;
                return resolve();
            }).catch(function (err) {
                _this.getSentFriendRequestsError = true;
                reject(null);
            });
        });
    };
    GraphService.prototype.getFriendRequests = function (rid) {
        var _this = this;
        if (rid === void 0) { rid = null; }
        return new Promise(function (resolve, reject) {
            var rids = [rid || _this.generateRid(_this.bulletinSecretService.identity.username_signature, _this.bulletinSecretService.identity.username_signature, _this.settingsService.collections.CONTACT)];
            _this.endpointRequest('get-graph-collection', null, rids)
                .then(function (data) {
                _this.parseFriendRequests(data.collection);
                _this.getFriendRequestsError = false;
                return resolve();
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
            _this.sortAlpha(friends, 'username');
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
            return _this.parseGroups(data.collection, root, collectionName);
        }).then(function (groups) {
            _this.getGroupsRequestsError = false;
            return groups;
        });
    };
    GraphService.prototype.getMail = function (rid, collection) {
        var _this = this;
        if (collection === void 0) { collection = this.settingsService.collections.MAIL; }
        //get messages for a specific friend
        return new Promise(function (resolve, reject) {
            _this.endpointRequest('get-graph-collection', null, rid)
                .then(function (data) {
                return _this.parseMail(data.collection, 'new_mail_counts', 'new_mail_count', undefined, collection, 'last_mail_height');
            })
                .then(function (mail) {
                _this.graph.mail = _this.graph.mail.concat(mail);
                _this.graph.mail = _this.toDistinct(_this.graph.mail, 'id');
                _this.sortInt(_this.graph.mail, 'time');
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
                return _this.parseMail(data.collection, 'new_sent_mail_counts', 'new_sent_mail_count', undefined, _this.settingsService.collections.MAIL, 'last_sent_mail_height');
            })
                .then(function (mail) {
                _this.graph.mail = mail;
                _this.sortInt(_this.graph.mail, 'time');
                _this.getMailError = false;
                return resolve(mail);
            }).catch(function (err) {
                _this.getMailError = true;
                reject(err);
            });
        });
    };
    GraphService.prototype.getAssets = function (rids) {
        var _this = this;
        var collection = this.settingsService.collections.ASSET;
        return this.endpointRequest('get-graph-collection', null, rids)
            .then(function (data) {
            return _this.parseAssets(data.collection);
        });
    };
    GraphService.prototype.getSmartContracts = function (market, rid, collectionName) {
        var _this = this;
        if (rid === void 0) { rid = null; }
        if (collectionName === void 0) { collectionName = this.settingsService.collections.SMART_CONTRACT; }
        var root = !rid;
        rid = rid || this.generateRid(market.username_signature, market.username_signature, collectionName);
        return this.endpointRequest('get-graph-collection', null, rid)
            .then(function (data) {
            return _this.parseSmartContracts(data.collection, market);
        }).then(function (groups) {
            _this.getGroupsRequestsError = false;
            return groups;
        });
    };
    GraphService.prototype.getBids = function (requested_rid, market) {
        var _this = this;
        return this.endpointRequest('get-graph-collection', null, requested_rid)
            .then(function (data) {
            return _this.parseBids(data.collection, market);
        });
    };
    GraphService.prototype.getAffiliates = function (requested_rid, market) {
        var _this = this;
        return this.endpointRequest('get-graph-collection', null, requested_rid)
            .then(function (data) {
            return _this.parseAffiliates(data.collection, market);
        });
    };
    GraphService.prototype.prepareMailItems = function (label) {
        var _this = this;
        return this.graph.mail.filter(function (item) {
            if (label === 'Sent' && item.public_key === _this.bulletinSecretService.identity.public_key)
                return true;
            if (label === 'Inbox' && item.public_key !== _this.bulletinSecretService.identity.public_key)
                return true;
        }).map(function (item) {
            return _this.prepareMailItem(item, label);
        });
    };
    GraphService.prototype.prepareMailItem = function (item, label) {
        var group = this.getIdentityFromTxn(this.groups_indexed[item.requested_rid], this.settingsService.collections.GROUP);
        var friend = this.getIdentityFromTxn(this.friends_indexed[item.rid], this.settingsService.collections.CONTACT);
        var identity = group || friend;
        var collection = group ? this.settingsService.collections.GROUP_MAIL : this.settingsService.collections.MAIL;
        var sender;
        if (item.relationship[collection].sender) {
            sender = item.relationship[collection].sender;
        }
        else if (item.public_key === this.bulletinSecretService.identity.public_key && label === 'Inbox') {
            sender = this.bulletinSecretService.identity;
        }
        else {
            sender = {
                username: identity.username,
                username_signature: identity.username_signature,
                public_key: identity.public_key
            };
        }
        var datetime = new Date(parseInt(item.time) * 1000);
        return {
            sender: sender,
            group: group || null,
            subject: item.relationship[collection].subject,
            body: item.relationship[collection].body,
            datetime: datetime.toLocaleDateString() + ' ' + datetime.toLocaleTimeString(),
            id: item.id,
            thread: item.relationship.thread,
            message_type: item.relationship[collection].message_type,
            event_datetime: item.relationship[collection].event_datetime,
            skylink: item.relationship[collection].skylink,
            filename: item.relationship[collection].filename,
            rid: item.rid
        };
    };
    GraphService.prototype.getMessages = function (rid, collection, updateLastCollectionTime) {
        var _this = this;
        if (collection === void 0) { collection = this.settingsService.collections.CHAT; }
        if (updateLastCollectionTime === void 0) { updateLastCollectionTime = false; }
        if (typeof rid === 'string')
            rid = [rid];
        //get messages for a specific friend
        return this.endpointRequest('get-graph-collection', null, rid, null, updateLastCollectionTime)
            .then(function (data) {
            return _this.parseMessages(data.collection, data.new_count, 'new_messages_count', rid, collection, 'last_message_height');
        })
            .then(function (chats) {
            return new Promise(function (resolve, reject) {
                _this.graph.messages[rid] = chats;
                _this.getMessagesError = false;
                return resolve(chats);
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
                return resolve(newChats);
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
                return _this.parseMessages(data.messages, 'sent_messages_counts', 'sent_messages_count', null, _this.settingsService.collections.CHAT, 'last_message_height');
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
                return _this.parseGroupMessages(key, data.messages, 'new_group_messages_counts', 'new_group_messages_count', rid, [_this.settingsService.collections.GROUP_CHAT, _this.settingsService.collections.GROUP_CHAT_FILE_NAME], 'last_group_message_height');
            })
                .then(function (chats) {
                if (!_this.graph.messages) {
                    _this.graph.messages = {};
                }
                if (choice_rid && chats[choice_rid]) {
                    _this.graph.messages[choice_rid] = chats[choice_rid];
                    _this.sortInt(_this.graph.messages[choice_rid], 'time', true);
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
                return resolve(newChats);
            }).catch(function (err) {
                _this.getNewMessagesError = true;
                reject(err);
            });
        });
    };
    GraphService.prototype.getSignIns = function (rids) {
        var _this = this;
        return this.endpointRequest('get-graph-collection', undefined, rids)
            .then(function (data) {
            _this.graph.signins = _this.parseMessages(data.collection, 'new_sign_ins_counts', 'new_sign_ins_count', rids, _this.settingsService.collections.WEB_CHALLENGE_RESPONSE, 'last_sign_in_height');
            _this.getSignInsError = false;
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
                return resolve(newSignIns);
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
                _this.graph.reacts = _this.parseMessages(data.reacts, 'new_reacts_counts', 'new_reacts_count', rid, _this.settingsService.collections.CHAT, 'last_react_height');
                _this.getReactsError = false;
                return resolve(data.reacts);
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
                _this.graph.comments = _this.parseMessages(data.reacts, 'new_comments_counts', 'new_comments_count', rid, _this.settingsService.collections.CHAT, 'last_comment_height');
                _this.getCommentsError = false;
                return resolve(data.comments);
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
                _this.graph.commentReacts = _this.parseMessages(data.reacts, 'new_comment_reacts_counts', 'new_comment_reacts_count', rid, _this.settingsService.collections.CHAT, 'last_comment_react_height');
                _this.getcommentReactsError = false;
                return resolve(data.comment_reacts);
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
                _this.graph.commentReplies = _this.parseMessages(data.reacts, 'new_comment_comments_counts', 'new_comment_comments_count', rid, _this.settingsService.collections.CHAT, 'last_comment_comment_height');
                _this.getcommentRepliesError = false;
                return resolve(data.comments);
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
    GraphService.prototype.getMyPages = function (rids) {
        var _this = this;
        return this.endpointRequest('get-graph-collection', undefined, rids)
            .then(function (data) {
            _this.graph.mypages = _this.parseMyPages(data.collection);
            _this.getMyPagesError = false;
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
                if (!relationship[this.settingsService.collections.CONTACT])
                    continue;
                friend_request.relationship = relationship;
                if (sent_friend_requestsObj[friend_request.rid]) {
                    delete friend_requestsObj[friend_request.rid];
                    delete sent_friend_requestsObj[friend_request.rid];
                    this.graph.friends.push(friend_request);
                    this.friends_indexed[friend_request.rid] = friend_request;
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
                    this.graph.friends.push(friend_requestsObj[friend_request.rid]);
                    this.friends_indexed[friend_request.rid] = friend_requestsObj[friend_request.rid];
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
                friend_requests.push(friend_requestsObj[arr_friend_request_keys[i]]);
            }
        }
        this.friend_request_count = friend_requests.length;
        if (this.platform.is('android') || this.platform.is('ios')) {
            this.badge.set(friend_requests.length);
        }
        this.graph.friend_requests = friend_requests;
        this.graph.sent_friend_requests = sent_friend_requests;
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
            return resolve(friends);
        });
    };
    GraphService.prototype.parseGroups = function (groups, root, collection) {
        var _this = this;
        if (root === void 0) { root = true; }
        if (collection === void 0) { collection = 'group'; }
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
                    if (bypassDecrypt) {
                        relationship = group.relationship[collection];
                    }
                    else {
                        relationship = JSON.parse(decrypted);
                        if (!relationship[collection])
                            continue;
                        if (relationship[collection].collection !== collection)
                            continue;
                        group['relationship'] = relationship;
                    }
                }
                catch (err) {
                    console.log(err);
                    failed = true;
                }
                if (failed && _this.groups_indexed[group.requester_rid]) {
                    try {
                        var parentGroup = _this.getIdentityFromTxn(_this.groups_indexed[group.requester_rid], collection);
                        if (parentGroup.public_key !== group.public_key)
                            continue;
                        if (typeof group.relationship == 'object') {
                            bypassDecrypt = true;
                        }
                        else {
                            decrypted = _this.shared_decrypt(parentGroup.username_signature, group.relationship);
                        }
                        var relationship;
                        if (bypassDecrypt) {
                            relationship = group.relationship[collection];
                        }
                        else {
                            relationship = JSON.parse(decrypted);
                            if (!relationship[collection])
                                continue;
                            if (!relationship[collection].parent)
                                continue;
                            if (relationship[collection].collection !== collection)
                                continue;
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
                    _this.graph[collection + 's'].push(group);
                }
                _this.groups_indexed[group.requested_rid] = group;
                var group_username_signature = void 0;
                if (group.relationship[_this.settingsService.collections.SMART_CONTRACT]) {
                    group_username_signature = group.relationship[collection].identity.username_signature;
                }
                else {
                    group_username_signature = group.relationship[collection].username_signature;
                }
                if (collection === _this.settingsService.collections.GROUP) {
                    _this.groups_indexed[_this.generateRid(group_username_signature, group_username_signature, _this.settingsService.collections.GROUP_CHAT)] = group;
                    _this.groups_indexed[_this.generateRid(group_username_signature, group_username_signature, _this.settingsService.collections.GROUP_MAIL)] = group;
                    _this.groups_indexed[_this.generateRid(group_username_signature, group_username_signature, _this.settingsService.collections.CALENDAR)] = group;
                    _this.groups_indexed[_this.generateRid(group_username_signature, group_username_signature, _this.settingsService.collections.GROUP_CALENDAR)] = group;
                }
                _this.groups_indexed[_this.generateRid(group_username_signature, group_username_signature, group_username_signature)] = group;
                try {
                    if (!relationship.parent && !relationship[_this.settingsService.collections.SMART_CONTRACT]) {
                        promises.push(_this.getGroups(_this.generateRid(group_username_signature, group_username_signature, group_username_signature), collection, true));
                    }
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
                    if (!_this.groups_indexed[arr_friends_keys[i]].relationship[_this.settingsService.collections.GROUP] || used_username_signatures.indexOf(_this.groups_indexed[arr_friends_keys[i]].relationship[_this.settingsService.collections.GROUP].username_signature) > -1) {
                        continue;
                    }
                    else {
                        groups.push(_this.groups_indexed[arr_friends_keys[i]]);
                        used_username_signatures.push(_this.groups_indexed[arr_friends_keys[i]].relationship[_this.settingsService.collections.GROUP].username_signature);
                    }
                }
            }
            return Promise.all(promises)
                .then(function (results) {
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
                        var identity_1 = _this.getIdentityFromTxn(_this.groups_indexed[message.requested_rid], _this.settingsService.collections.GROUP);
                        var decrypted = _this.shared_decrypt(identity_1.username_signature, message.relationship);
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
                        }
                        continue dance;
                    }
                }
            }
            return resolve(chats);
        });
    };
    GraphService.prototype.parseMessages = function (messages, newCount, graphCount, rid, messageType, messageHeightType) {
        var _this = this;
        if (rid === void 0) { rid = null; }
        if (messageType === void 0) { messageType = null; }
        if (messageHeightType === void 0) { messageHeightType = null; }
        this[graphCount] = 0;
        return new Promise(function (resolve, reject) {
            var chats = [];
            dance: for (var i = 0; i < messages.length; i++) {
                var message = messages[i];
                if (rid && message.rid !== rid && rid.indexOf(message.rid) === -1 && rid.indexOf(message.requested_rid) === -1)
                    continue;
                if (!message.rid && !message.requested_rid)
                    continue;
                if (message.dh_public_key)
                    continue;
                if (_this.groups_indexed[message.requested_rid]) {
                    var group = _this.getIdentityFromTxn(_this.groups_indexed[message.requested_rid], _this.settingsService.collections.GROUP);
                    if (i === 0)
                        _this.counts[group.username_signature] = newCount;
                    try {
                        _this.counts[group.username_signature] = typeof _this.counts[group.username_signature] === 'number' && _this.counts[group.username_signature] > 0 ? _this.counts[group.username_signature] : newCount;
                        var decrypted = _this.shared_decrypt(group.username_signature, message.relationship);
                    }
                    catch (error) {
                        _this.counts[group.username_signature]--;
                        continue;
                    }
                    try {
                        var messageJson = JSON.parse(decrypted);
                    }
                    catch (err) {
                        _this.counts[group.username_signature]--;
                        continue;
                    }
                    if (messageJson[messageType]) {
                        message.relationship = messageJson;
                        messages[message.requested_rid] = message;
                        try {
                            message.relationship[messageType] = JSON.parse(Base64.decode(messageJson[messageType]));
                            message.relationship.isInvite = true;
                            if (typeof message.relationship[messageType] !== 'string')
                                continue dance;
                        }
                        catch (err) {
                            //not an invite, do nothing
                        }
                        chats.push(message);
                    }
                    continue dance;
                }
                else {
                    var friend = _this.getIdentityFromMessageTransaction(message);
                    if (i === 0)
                        _this.counts[friend.username_signature] = newCount;
                    if (!_this.stored_secrets[message.rid])
                        continue;
                    var shared_secret = _this.stored_secrets[message.rid][j];
                    //hopefully we've prepared the stored_secrets option before getting here
                    //by calling getSentFriendRequests and getFriendRequests
                    for (var j = 0; j < _this.stored_secrets[message.rid].length; j++) {
                        var shared_secret = _this.stored_secrets[message.rid][j];
                        try {
                            _this.counts[friend.username_signature] = typeof _this.counts[friend.username_signature] === 'number' && _this.counts[friend.username_signature] > 0 ? _this.counts[friend.username_signature] : newCount;
                            var decrypted = _this.shared_decrypt(shared_secret.shared_secret, message.relationship);
                        }
                        catch (error) {
                            friend && _this.counts[friend.username_signature]--;
                            continue;
                        }
                        try {
                            var messageJson = JSON.parse(decrypted);
                        }
                        catch (err) {
                            friend && _this.counts[friend.username_signature]--;
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
                        }
                        continue dance;
                    }
                }
            }
            return resolve(chats);
        });
    };
    GraphService.prototype.parseNewMessages = function (messages, graphCounts, graphCount, heightType) {
        this[graphCount] = 0;
        this[graphCounts] = {};
        var public_key = this.bulletinSecretService.key.getPublicKeyBuffer().toString('hex');
        return new Promise(function (resolve, reject) {
            var new_messages = [];
            for (var i = 0; i < messages.length; i++) {
                var message = messages[i];
                if (message.public_key != public_key) {
                    new_messages.push(message);
                }
            }
            return resolve(new_messages);
        });
    };
    GraphService.prototype.parseGroupMessages = function (key, messages, graphCounts, graphCount, rid, messageType, messageHeightType) {
        var _this = this;
        if (rid === void 0) { rid = null; }
        if (messageType === void 0) { messageType = null; }
        if (messageHeightType === void 0) { messageHeightType = null; }
        this[graphCount] = 0;
        return new Promise(function (resolve, reject) {
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
                }
            }
            return resolve(chats);
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
                var group = this.getIdentityFromTxn(this.groups_indexed[event_1.requested_rid], this.settingsService.collections.GROUP);
                if (group) {
                    decrypted = this.shared_decrypt(group.username_signature, event_1.relationship);
                }
                else if (this.friends_indexed[event_1.rid]) {
                    if (!this.stored_secrets[event_1.rid])
                        continue;
                    var shared_secret = this.stored_secrets[event_1.rid][0].shared_secret;
                    decrypted = this.shared_decrypt(shared_secret, event_1.relationship);
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
            if (messageJson[this.settingsService.collections.CALENDAR]) {
                event_1.relationship = messageJson;
                event_1.relationship[this.settingsService.collections.CALENDAR].event_datetime = new Date(event_1.relationship[this.settingsService.collections.CALENDAR].event_datetime);
                eventsOut.push(event_1);
            }
            else if (messageJson[this.settingsService.collections.GROUP_CALENDAR]) {
                event_1.relationship = messageJson;
                event_1.relationship[this.settingsService.collections.GROUP_CALENDAR].event_datetime = new Date(event_1.relationship[this.settingsService.collections.GROUP_CALENDAR].event_datetime);
                eventsOut.push(event_1);
            }
            else if (messageJson.event) {
                event_1.relationship = messageJson;
                event_1.relationship.event.event_datetime = new Date(event_1.relationship.event.event_datetime);
                eventsOut.push(event_1);
            }
        }
        return eventsOut;
    };
    GraphService.prototype.parseMyPages = function (mypages) {
        var mypagesOut = [];
        var myRids = this.generateRids(this.bulletinSecretService.identity);
        for (var i = 0; i < mypages.length; i++) {
            //hopefully we've prepared the stored_secrets option before getting here
            //by calling getSentFriendRequests and getFriendRequests
            var mypage = mypages[i];
            var decrypted = void 0;
            try {
                decrypted = this.decrypt(mypage.relationship);
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
            if (messageJson[this.settingsService.collections.WEB_PAGE]) {
                mypage.relationship = messageJson;
                mypagesOut.push(mypage);
            }
        }
        return mypagesOut;
    };
    GraphService.prototype.parseAssets = function (assets) {
        var assetsOut = [];
        for (var i = 0; i < assets.length; i++) {
            //hopefully we've prepared the stored_secrets option before getting here
            //by calling getSentFriendRequests and getFriendRequests
            var asset = assets[i];
            var decrypted = void 0;
            try {
                decrypted = this.decrypt(asset.relationship);
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
            if (messageJson[this.settingsService.collections.ASSET]) {
                asset.relationship = messageJson;
                assetsOut.push(asset);
            }
        }
        return assetsOut;
    };
    GraphService.prototype.parseSmartContracts = function (smartContracts, market) {
        var smartContractsOut = [];
        for (var i = 0; i < smartContracts.length; i++) {
            try {
                var smartContractTxn = smartContracts[i];
                var smartContract = smartContractTxn.relationship[this.settingsService.collections.SMART_CONTRACT];
                if (!smartContract)
                    continue;
                if (smartContract.asset) {
                    var asset = this.shared_decrypt(market.username_signature, smartContract.asset);
                    smartContract.asset = JSON.parse(asset);
                }
                if (smartContract.target) {
                    var target = this.shared_decrypt(market.username_signature, smartContract.target);
                    smartContract.target = JSON.parse(target);
                }
                var creator = this.shared_decrypt(market.username_signature, smartContract.creator);
                smartContract.creator = JSON.parse(creator);
                smartContractTxn.relationship[this.settingsService.collections.SMART_CONTRACT] = smartContract;
                smartContractsOut.push(smartContractTxn);
            }
            catch (err) {
                console.log(err);
            }
        }
        return smartContractsOut;
    };
    GraphService.prototype.parsePromotion = function (promotionTxn, market) {
        try {
            var target = this.shared_decrypt(market.username_signature, promotionTxn.relationship);
            promotionTxn.relationship = JSON.parse(target);
        }
        catch (err) {
            console.log(err);
        }
        return promotionTxn;
    };
    GraphService.prototype.parseBids = function (bids, market) {
        var bidsOut = [];
        for (var i = 0; i < bids.length; i++) {
            try {
                var bid = bids[i];
                bid.relationship = this.shared_decrypt(market.username_signature, bid.relationship);
                bid.relationship = JSON.parse(bid.relationship);
                bidsOut.push(bid);
            }
            catch (err) {
                console.log(err);
            }
        }
        return bidsOut;
    };
    GraphService.prototype.parseAffiliates = function (affiliates, market) {
        var affiliatesOut = [];
        for (var i = 0; i < affiliates.length; i++) {
            try {
                var affiliate = affiliates[i];
                affiliate.relationship = this.shared_decrypt(market.username_signature, affiliate.relationship);
                affiliate.relationship = JSON.parse(affiliate.relationship);
                affiliatesOut.push(affiliate);
            }
            catch (err) {
                console.log(err);
            }
        }
        return affiliatesOut;
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
            return resolve();
        });
    };
    GraphService.prototype.getSharedSecretForRid = function (rid) {
        var _this = this;
        return new Promise(function (resolve, reject) {
            _this.getSharedSecrets()
                .then(function () {
                if (_this.stored_secrets[rid] && _this.stored_secrets[rid].length > 0) {
                    return resolve(_this.stored_secrets[rid][0]);
                }
                else {
                    reject('no shared secret found for rid: ' + rid);
                }
            });
        });
    };
    GraphService.prototype.createGroup = function (groupname, parentGroup, extraData, collectionName) {
        var _this = this;
        if (parentGroup === void 0) { parentGroup = null; }
        if (extraData === void 0) { extraData = {}; }
        if (collectionName === void 0) { collectionName = 'group'; }
        var parentIdentity = this.getIdentityFromTxn(parentGroup);
        if (!groupname)
            return new Promise(function (resolve, reject) { reject('username missing'); });
        if (parentIdentity && parentIdentity.public_key !== this.bulletinSecretService.identity.public_key)
            return new Promise(function (resolve, reject) { reject('you cannot create a subgroup unless you are the owner of the group.'); });
        if (parentIdentity && parentIdentity.username === groupname)
            return new Promise(function (resolve, reject) { reject('you cannot create a subgroup with the same name as the parent group.'); });
        var username_signature = foobar.base64.fromByteArray(this.bulletinSecretService.key.sign(foobar.bitcoin.crypto.sha256(groupname)).toDER());
        var relationship = {
            username: groupname,
            username_signature: username_signature,
            public_key: this.bulletinSecretService.identity.public_key,
            collection: this.settingsService.collections.GROUP
        };
        var info = __assign({}, extraData);
        info[collectionName] = relationship;
        if (parentIdentity) {
            relationship.parent = {
                username: parentIdentity.username,
                username_signature: parentIdentity.username_signature,
                public_key: parentIdentity.public_key,
                collection: this.settingsService.collections.GROUP
            };
        }
        return this.transactionService.generateTransaction({
            relationship: info,
            to: this.bulletinSecretService.publicKeyToAddress(this.bulletinSecretService.identity.public_key),
            requester_rid: this.generateRid(parentIdentity ? parentIdentity.username_signature : this.bulletinSecretService.identity.username_signature, parentIdentity ? parentIdentity.username_signature : this.bulletinSecretService.identity.username_signature, parentIdentity ? parentIdentity.username_signature : collectionName),
            requested_rid: this.generateRid(username_signature, username_signature, parentIdentity ? parentIdentity.username_signature : collectionName),
            rid: this.generateRid(this.bulletinSecretService.identity.username_signature, username_signature),
            group: true
        }).then(function (txn) {
            return _this.transactionService.sendTransaction();
        }).then(function () {
            return _this.getGroups(null, relationship.collection, true);
        }).then(function () {
            return new Promise(function (resolve, reject) {
                return resolve({
                    username: groupname,
                    username_signature: username_signature,
                    public_key: _this.bulletinSecretService.identity.public_key,
                });
            });
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
                    return resolve({
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
        requester_rid = requester_rid || this.generateRid(this.bulletinSecretService.identity.username_signature, this.bulletinSecretService.identity.username_signature, this.settingsService.collections.CONTACT);
        requested_rid = requested_rid || this.generateRid(identity.username_signature, identity.username_signature, this.settingsService.collections.CONTACT);
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
        var myIdentity = this.bulletinSecretService.cloneIdentity();
        myIdentity.collection = this.settingsService.collections.CONTACT;
        var info = {
            dh_private_key: dh_private_key
        };
        info[this.settingsService.collections.CONTACT] = myIdentity;
        return this.transactionService.generateTransaction({
            relationship: info,
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
    GraphService.prototype.addGroup = function (identity, rid, requester_rid, requested_rid, refresh) {
        var _this = this;
        if (rid === void 0) { rid = ''; }
        if (requester_rid === void 0) { requester_rid = ''; }
        if (requested_rid === void 0) { requested_rid = ''; }
        if (refresh === void 0) { refresh = true; }
        identity.collection = identity.parent ? identity.parent.username_signature : identity.collection || this.settingsService.collections.GROUP;
        rid = rid || this.generateRid(this.bulletinSecretService.identity.username_signature, identity.username_signature);
        requester_rid = requester_rid || this.generateRid(this.bulletinSecretService.identity.username_signature, this.bulletinSecretService.identity.username_signature, identity.collection);
        requested_rid = requested_rid || this.generateRid(identity.parent ? identity.collection : identity.username_signature, identity.parent ? identity.collection : identity.username_signature, identity.collection);
        if (requester_rid && requested_rid) {
            // get rid from bulletin secrets
        }
        else {
            requester_rid = '';
            requested_rid = '';
        }
        if (this.groups_indexed[requested_rid]) {
            return new Promise(function (resolve, reject) {
                return resolve(identity);
            });
        }
        var info = {};
        info[identity.collection] = identity;
        return this.transactionService.generateTransaction({
            rid: rid,
            relationship: info,
            requested_rid: requested_rid,
            requester_rid: requester_rid,
            to: this.bulletinSecretService.publicKeyToAddress(identity.public_key)
        })
            .then(function (txn) {
            return _this.transactionService.sendTransaction(txn);
        }).then(function () {
            return refresh ? _this.getGroups(null, identity.collection, true) : null;
        }).then(function () {
            return new Promise(function (resolve, reject) {
                return resolve(identity);
            });
        });
    };
    GraphService.prototype.getPromotion = function (promo_code) {
        var _this = this;
        var promotion;
        return this.endpointRequest('get-graph-collection', null, [promo_code]) //get promotion
            .then(function (data) {
            if (!data.collection[0])
                throw Error('promotion does not exist');
            promotion = data.collection[0];
            return _this.endpointRequest('get-graph-collection', null, [data.collection[0].requested_rid]); // get smart contract
        })
            .then(function (data) {
            if (!data.collection[0])
                throw Error('smart contract does not exist');
            var smart_contracts = data.collection.filter(function (item) {
                return !!item.relationship[_this.settingsService.collections.SMART_CONTRACT];
            });
            if (!smart_contracts[0])
                throw Error('smart contract does not exist');
            var market_rid = smart_contracts[0].relationship[_this.settingsService.collections.SMART_CONTRACT].market;
            var market = _this.groups_indexed[market_rid].relationship[_this.settingsService.collections.MARKET];
            return _this.parsePromotion(promotion, market);
        })
            .then(function (promotion) {
            return promotion;
        });
    };
    GraphService.prototype.publicDecrypt = function (message) {
        var decrypted = Object(__WEBPACK_IMPORTED_MODULE_11_eciesjs__["decrypt"])(this.bulletinSecretService.key.d.toHex(), Buffer.from(this.hexToByteArray(message))).toString();
        return decrypted;
    };
    GraphService.prototype.generateRids = function (identity, identity2, collection) {
        if (identity2 === void 0) { identity2 = null; }
        if (collection === void 0) { collection = null; }
        identity2 = identity2 || this.bulletinSecretService.identity;
        var rid = this.generateRid(identity.username_signature, identity2.username_signature);
        var requested_rid = this.generateRid(identity.username_signature, identity.username_signature, identity.collection);
        var requester_rid = this.generateRid(identity2.username_signature, identity2.username_signature, collection || identity2.collection);
        return {
            rid: rid,
            requested_rid: requested_rid,
            requester_rid: requester_rid
        };
    };
    GraphService.prototype.isMe = function (identity) {
        if (!identity)
            return false;
        return identity.username_signature === this.bulletinSecretService.identity.username_signature;
    };
    GraphService.prototype.isAdded = function (identity) {
        if (!identity)
            return false;
        var rids = this.generateRids(identity);
        var addedToGroups = this.isChild(identity) ?
            !!(this.groups_indexed[rids.rid] || this.groups_indexed[rids.requested_rid] || this.groups_indexed[this.generateRid(identity.parent ? identity.parent.username_signature : identity.username_signature, identity.parent ? identity.parent.username_signature : identity.username_signature, identity.parent.username_signature)])
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
        return identity.collection && identity.collection !== this.settingsService.collections.CONTACT;
    };
    GraphService.prototype.isChild = function (identity) {
        if (!identity)
            return false;
        return !!identity.parent;
    };
    GraphService.prototype.sortInt = function (list, key, reverse) {
        if (reverse === void 0) { reverse = false; }
        list.sort(function (a, b) {
            if (parseInt(a[key]) > parseInt(b[key]))
                return reverse ? 1 : -1;
            if (parseInt(a[key]) < parseInt(b[key]))
                return reverse ? -1 : 1;
            return 0;
        });
    };
    GraphService.prototype.sortAlpha = function (list, key, reverse) {
        if (reverse === void 0) { reverse = false; }
        list.sort(function (a, b) {
            if (a[key] < b[key])
                return reverse ? 1 : -1;
            if (a[key] > b[key])
                return reverse ? -1 : 1;
            return 0;
        });
    };
    GraphService.prototype.sortTxnsByUsername = function (list, reverse, collection) {
        var _this = this;
        if (reverse === void 0) { reverse = false; }
        if (collection === void 0) { collection = null; }
        list.sort(function (a, b) {
            var ausername = _this.getIdentityFromTxn(a, collection);
            var busername = _this.getIdentityFromTxn(b, collection);
            if (ausername < busername)
                return reverse ? 1 : -1;
            if (ausername > busername)
                return reverse ? -1 : 1;
            return 0;
        });
    };
    GraphService.prototype.toDistinct = function (list, key) {
        var hashMap = {};
        for (var i = 0; i < list.length; i++) {
            hashMap[list[i][key]] = list[i];
        }
        var newList = [];
        for (var i = 0; i < Object.keys(hashMap).length; i++) {
            newList.push(hashMap[Object.keys(hashMap)[i]]);
        }
        return newList;
    };
    GraphService.prototype.toIdentity = function (identity) {
        if (!identity)
            return {};
        var iden = {
            username: identity.username,
            username_signature: identity.username_signature,
            public_key: identity.public_key
        };
        if (identity.parent) {
            iden.parent = identity.parent;
        }
        if (identity.collection) {
            iden.collection = identity.collection;
        }
        if (identity.skylink) {
            iden.skylink = identity.skylink;
        }
        return iden;
    };
    GraphService.prototype.getIdentityFromMessageTransaction = function (item) {
        if (!item)
            return;
        var group = this.groups_indexed[item.requested_rid];
        if (group) {
            return this.getIdentityFromTxn(group, this.settingsService.collections.GROUP);
        }
        var friend = this.friends_indexed[item.rid];
        if (friend) {
            return this.getIdentityFromTxn(friend, this.settingsService.collections.CONTACT);
        }
    };
    GraphService.prototype.getIdentityFromTxn = function (item, collection) {
        if (collection === void 0) { collection = null; }
        if (!item)
            return;
        var col = collection || this.getNewTxnCollection(item);
        return item.relationship[col];
    };
    GraphService.prototype.getParentIdentityFromTxn = function (item, collection) {
        if (collection === void 0) { collection = null; }
        if (!item)
            return;
        var identity = this.getIdentityFromTxn(item, collection);
        return identity && identity.parent;
    };
    GraphService.prototype.getNewTxnCollection = function (txn) {
        for (var i = 0; i < Object.keys(this.settingsService.collections).length; i++) {
            var collection = this.settingsService.collections[Object.keys(this.settingsService.collections)[i]];
            var rid = this.generateRid(this.bulletinSecretService.identity.username_signature, this.bulletinSecretService.identity.username_signature, collection);
            if (txn.rid === rid ||
                txn.requester_rid === rid ||
                txn.requested_rid === rid) {
                return collection;
            }
            if (txn.relationship[collection])
                return collection;
        }
        var collections = [
            this.settingsService.collections.GROUP_CHAT,
            this.settingsService.collections.GROUP_MAIL,
            this.settingsService.collections.GROUP_CALENDAR
        ];
        for (var j = 0; j < Object.keys(this.groups_indexed).length; j++) {
            var group = this.getIdentityFromTxn(this.groups_indexed[Object.keys(this.groups_indexed)[j]], this.settingsService.collections.GROUP);
            for (var i = 0; i < collections.length; i++) {
                var collection = collections[i];
                var rid = this.generateRid(group.username_signature, group.username_signature, collection);
                if (txn.rid === rid ||
                    txn.requester_rid === rid ||
                    txn.requested_rid === rid) {
                    return collection;
                }
            }
        }
        return false;
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
            _this.ahttp.get('https://centeridentity.com/sia-download?skylink=' + skylink)
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
            __WEBPACK_IMPORTED_MODULE_10__wallet_service__["a" /* WalletService */],
            __WEBPACK_IMPORTED_MODULE_7_ionic_angular__["b" /* Events */]])
    ], GraphService);
    return GraphService;
}());

//# sourceMappingURL=graph.service.js.map
/* WEBPACK VAR INJECTION */}.call(__webpack_exports__, __webpack_require__(7).Buffer))

/***/ }),

/***/ 20:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* WEBPACK VAR INJECTION */(function(Buffer) {/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return TransactionService; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__bulletinSecret_service__ = __webpack_require__(14);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__settings_service__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__angular_http__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5_eciesjs__ = __webpack_require__(353);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5_eciesjs___default = __webpack_require__.n(__WEBPACK_IMPORTED_MODULE_5_eciesjs__);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__smartContract_service__ = __webpack_require__(68);
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
    function TransactionService(walletService, bulletinSecretService, ahttp, settingsService, smartContractService) {
        this.walletService = walletService;
        this.bulletinSecretService = bulletinSecretService;
        this.ahttp = ahttp;
        this.settingsService = settingsService;
        this.smartContractService = smartContractService;
        this.info = null;
        this.transaction = null;
        this.key = null;
        this.xhr = null;
        this.rid = null;
        this.callbackurl = null;
        this.blockchainurl = null;
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
            var version = 3;
            _this.key = _this.bulletinSecretService.key;
            _this.username = _this.bulletinSecretService.username;
            _this.recipient_identity = info.recipient_identity;
            _this.txnattempts = [12, 5, 4];
            _this.cbattempts = [12, 5, 4];
            _this.info = info;
            _this.unspent_transaction_override = _this.info.unspent_transaction;
            _this.blockchainurl = _this.info.blockchainurl;
            _this.callbackurl = _this.info.callbackurl;
            _this.to = _this.info.to;
            _this.value = parseFloat(_this.info.value);
            _this.transaction = {
                version: 3,
                rid: _this.info.rid,
                fee: 0.00,
                outputs: [],
                requester_rid: typeof _this.info.requester_rid == 'undefined' ? '' : _this.info.requester_rid,
                requested_rid: typeof _this.info.requested_rid == 'undefined' ? '' : _this.info.requested_rid,
                time: parseInt(((+new Date()) / 1000).toString()).toString(),
                public_key: _this.key.getPublicKeyBuffer().toString('hex')
            };
            if (_this.info.outputs) {
                _this.transaction.outputs = _this.info.outputs;
            }
            if (_this.info.dh_public_key && _this.info.relationship.dh_private_key) {
                _this.transaction.dh_public_key = _this.info.dh_public_key;
            }
            if (_this.to) {
                _this.transaction.outputs.push({
                    to: _this.to,
                    value: _this.value || 0
                });
            }
            var transaction_total = 0;
            if (_this.transaction.outputs.length > 0) {
                for (var i_1 = 0; i_1 < _this.transaction.outputs.length; i_1++) {
                    transaction_total += parseFloat(_this.transaction.outputs[i_1].value);
                }
                transaction_total += parseFloat(_this.transaction.fee);
            }
            else {
                transaction_total = parseFloat(_this.transaction.fee);
            }
            var inputs_hashes_concat = '';
            if ((_this.info.relationship && _this.info.relationship.dh_private_key && _this.walletService.wallet.balance < transaction_total) /* || this.walletService.wallet.unspent_transactions.length == 0*/) {
                reject("not enough money");
                return;
            }
            else {
                if (transaction_total > 0) {
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
                    if (input_sum < transaction_total) {
                        return reject('Insufficient funds');
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
                    inputs_hashes_concat = inputs_hashes_arr.join('');
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
                    outputs_hashes_concat +
                    version).toString('hex');
            }
            else if (_this.info.relationship[_this.settingsService.collections.SMART_CONTRACT]) {
                //creating smart contract instance
                _this.transaction.relationship = _this.info.relationship;
                var smart_contract = _this.info.relationship[_this.settingsService.collections.SMART_CONTRACT];
                if (smart_contract.asset) {
                    smart_contract.asset = _this.shared_encrypt(_this.info.shared_secret, JSON.stringify(smart_contract.asset));
                }
                if (smart_contract.target) {
                    smart_contract.target = _this.shared_encrypt(_this.info.shared_secret, JSON.stringify(smart_contract.target));
                }
                _this.transaction.relationship[_this.settingsService.collections.SMART_CONTRACT].creator = _this.shared_encrypt(_this.info.shared_secret, JSON.stringify(_this.transaction.relationship[_this.settingsService.collections.SMART_CONTRACT].creator));
                var hash = foobar.bitcoin.crypto.sha256(_this.transaction.public_key +
                    _this.transaction.time +
                    _this.transaction.rid +
                    _this.smartContractService.toString(_this.info.relationship[_this.settingsService.collections.SMART_CONTRACT]) +
                    _this.transaction.fee.toFixed(8) +
                    _this.transaction.requester_rid +
                    _this.transaction.requested_rid +
                    inputs_hashes_concat +
                    outputs_hashes_concat +
                    version).toString('hex');
            }
            else if (_this.info.relationship[_this.settingsService.collections.CALENDAR] ||
                _this.info.relationship[_this.settingsService.collections.CHAT] ||
                _this.info.relationship[_this.settingsService.collections.GROUP_CALENDAR] ||
                _this.info.relationship[_this.settingsService.collections.GROUP_CHAT] ||
                _this.info.relationship[_this.settingsService.collections.GROUP_MAIL] ||
                _this.info.relationship[_this.settingsService.collections.MAIL]) {
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
                    outputs_hashes_concat +
                    version).toString('hex');
            }
            else if (_this.info.relationship[_this.settingsService.collections.WEB_PAGE_REQUEST]) {
                // sign in
                _this.transaction.relationship = _this.shared_encrypt(_this.info.shared_secret, JSON.stringify(_this.info.relationship));
                hash = foobar.bitcoin.crypto.sha256(_this.transaction.public_key +
                    _this.transaction.time +
                    _this.transaction.rid +
                    _this.transaction.relationship +
                    _this.transaction.fee.toFixed(8) +
                    _this.transaction.requester_rid +
                    _this.transaction.requested_rid +
                    inputs_hashes_concat +
                    outputs_hashes_concat +
                    version).toString('hex');
            }
            else if (_this.info.relationship.wif) {
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
                    outputs_hashes_concat +
                    version).toString('hex');
            }
            else if (_this.info.relationship[_this.settingsService.collections.GROUP]) {
                // join or create group
                if (_this.info.relationship[_this.settingsService.collections.GROUP].parent) {
                    _this.transaction.relationship = _this.shared_encrypt(_this.info.relationship[_this.settingsService.collections.GROUP].parent.username_signature, JSON.stringify(_this.info.relationship));
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
                    outputs_hashes_concat +
                    version).toString('hex');
            }
            else if (_this.info.relationship[_this.settingsService.collections.MARKET]) {
                // join or create market
                _this.transaction.relationship = _this.encrypt();
                hash = foobar.bitcoin.crypto.sha256(_this.transaction.public_key +
                    _this.transaction.time +
                    _this.transaction.rid +
                    _this.transaction.relationship +
                    _this.transaction.fee.toFixed(8) +
                    _this.transaction.requester_rid +
                    _this.transaction.requested_rid +
                    inputs_hashes_concat +
                    outputs_hashes_concat +
                    version).toString('hex');
            }
            else if (_this.info.relationship[_this.settingsService.collections.AFFILIATE] ||
                _this.info.relationship[_this.settingsService.collections.BID] ||
                _this.info.relationship[_this.settingsService.collections.WEB_CHALLENGE_REQUEST] ||
                _this.info.relationship[_this.settingsService.collections.WEB_CHALLENGE_RESPONSE] ||
                _this.info.relationship[_this.settingsService.collections.WEB_PAGE_REQUEST] ||
                _this.info.relationship[_this.settingsService.collections.WEB_PAGE_RESPONSE] ||
                _this.info.relationship[_this.settingsService.collections.WEB_SIGNIN_REQUEST] ||
                _this.info.relationship[_this.settingsService.collections.WEB_SIGNIN_RESPONSE]) {
                _this.transaction.relationship = _this.shared_encrypt(_this.info.shared_secret, JSON.stringify(_this.info.relationship));
                hash = foobar.bitcoin.crypto.sha256(_this.transaction.public_key +
                    _this.transaction.time +
                    _this.transaction.rid +
                    _this.transaction.relationship +
                    _this.transaction.fee.toFixed(8) +
                    _this.transaction.requester_rid +
                    _this.transaction.requested_rid +
                    inputs_hashes_concat +
                    outputs_hashes_concat +
                    version).toString('hex');
            }
            else if (_this.info.relationship[_this.settingsService.collections.WEB_PAGE] ||
                _this.info.relationship[_this.settingsService.collections.ASSET]) {
                // mypage
                _this.transaction.relationship = _this.encrypt();
                hash = foobar.bitcoin.crypto.sha256(_this.transaction.public_key +
                    _this.transaction.time +
                    _this.transaction.rid +
                    _this.transaction.relationship +
                    _this.transaction.fee.toFixed(8) +
                    _this.transaction.requester_rid +
                    _this.transaction.requested_rid +
                    inputs_hashes_concat +
                    outputs_hashes_concat +
                    version).toString('hex');
            }
            else {
                //straight transaction
                hash = foobar.bitcoin.crypto.sha256(_this.transaction.public_key +
                    _this.transaction.time +
                    (_this.transaction.rid || '') +
                    (_this.transaction.relationship || '') +
                    _this.transaction.fee.toFixed(8) +
                    (_this.transaction.requester_rid || '') +
                    (_this.transaction.requested_rid || '') +
                    inputs_hashes_concat +
                    outputs_hashes_concat +
                    version).toString('hex');
            }
            _this.transaction.hash = hash;
            var attempt = _this.txnattempts.pop();
            attempt = _this.cbattempts.pop();
            _this.transaction.id = _this.get_transaction_id(_this.transaction.hash, attempt);
            if (hash) {
                resolve(_this.transaction);
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
    TransactionService.prototype.sendTransaction = function (txn, transactionUrlOverride) {
        var _this = this;
        if (txn === void 0) { txn = null; }
        if (transactionUrlOverride === void 0) { transactionUrlOverride = undefined; }
        return new Promise(function (resolve, reject) {
            var url = '';
            url = (transactionUrlOverride || _this.settingsService.remoteSettings['transactionUrl']) + '?username_signature=' + _this.bulletinSecretService.username_signature + '&to=' + _this.key.getAddress() + '&username=' + _this.username;
            _this.ahttp.post(url, txn || _this.transaction)
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
            __WEBPACK_IMPORTED_MODULE_3__settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_6__smartContract_service__["a" /* SmartContractService */]])
    ], TransactionService);
    return TransactionService;
}());

//# sourceMappingURL=transaction.service.js.map
/* WEBPACK VAR INJECTION */}.call(__webpack_exports__, __webpack_require__(7).Buffer))

/***/ }),

/***/ 225:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return HomePage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__angular_forms__ = __webpack_require__(30);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2_ionic_angular__ = __webpack_require__(5);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__ionic_storage__ = __webpack_require__(48);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_bulletinSecret_service__ = __webpack_require__(14);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_graph_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__app_transaction_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__app_peer_service__ = __webpack_require__(226);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__list_list__ = __webpack_require__(69);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_10__profile_profile__ = __webpack_require__(70);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_11__app_opengraphparser_service__ = __webpack_require__(140);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_12__ionic_native_social_sharing__ = __webpack_require__(108);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_13__app_settings_service__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_14__app_firebase_service__ = __webpack_require__(231);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_15__angular_http__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_16__app_autocomplete_provider__ = __webpack_require__(110);
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
        this.createdCode = this.bulletinSecretService.identityJson();
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
            selector: 'page-home',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/home/home.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n  </ion-navbar>\n</ion-header>\n\n<ion-content padding>\n  <ion-spinner *ngIf="loading"></ion-spinner>\n  <ion-row>\n    <ion-col col-lg-12 col-md-12 col-sm-12 *ngIf="graphService.registrationStatus() === \'error\'">\n      Something went wrong with your registration, contact info@centeridentity.com for assistance.\n    </ion-col>\n    <ion-col col-lg-12 col-md-12 col-sm-12 *ngIf="graphService.registrationStatus() === \'pending\'">\n      Registration is pending approval.\n    </ion-col>\n    <ion-col col-lg-12 col-md-12 col-sm-12 *ngIf="graphService.registrationStatus() === \'complete\' && settingsService.remoteSettings.restricted">\n      <h1>Welcome!</h1>\n    </ion-col>\n    <ion-col col-lg-12 col-md-12 col-sm-12 *ngIf="!settingsService.remoteSettings.restricted">\n      <h1>Welcome!</h1>\n      <h4>Public identity (share this with everyone) <ion-spinner *ngIf="busy"></ion-spinner></h4>\n      <ion-item *ngIf="settingsService.remoteSettings.restricted">\n        <ion-textarea type="text" [(ngModel)]="identitySkylink" autoGrow="true" rows=1></ion-textarea>\n      </ion-item>\n      <ion-item *ngIf="!settingsService.remoteSettings.restricted">\n        <ion-textarea type="text" [value]="bulletinSecretService.identityJson()" autoGrow="true" rows=5></ion-textarea>\n      </ion-item>\n      <ion-item>\n        <ngx-qrcode [qrc-value]="createdCode"></ngx-qrcode>\n      </ion-item>\n    </ion-col>\n  </ion-row>\n  <ion-row *ngIf="settingsService.remoteSettings.restricted && bulletinSecretService.identity.type === \'admin\'">\n    <ion-col col-lg-6 col-md-6 col-sm-12>\n      <h3>Invite organizations</h3>\n      <ion-item>\n        <ion-label floating>Identifier <ion-spinner *ngIf="inviteBusy"></ion-spinner></ion-label>\n        <ion-input type="text" [(ngModel)]="organizationIdentifier"></ion-input>\n      </ion-item>\n      <ion-item>\n        <button ion-button large secondary (click)="addOrganization()" [disabled]="!organizationIdentifier || inviteBusy">\n          Add organization&nbsp;<ion-icon name="create"></ion-icon>\n        </button>\n      </ion-item>\n    </ion-col>\n    <ion-col col-lg-6 col-md-6 col-sm-12 *ngIf="invites">\n      <h3>Invites</h3>\n      <ion-list *ngFor="let invite of invites">\n        <ion-item ion-item>\n          <ion-icon name="person" item-start [color]="\'dark\'"></ion-icon>\n          {{invite.email}}\n        </ion-item>\n        <ion-item>\n          <ion-label floating>Invite code</ion-label>\n          <ion-input type="text" [value]="invite.skylink"></ion-input>\n        </ion-item>\n      </ion-list>\n    </ion-col>\n  </ion-row>\n  <ion-row *ngIf="settingsService.remoteSettings.restricted && bulletinSecretService.identity.type === \'organization\'">\n    <ion-col col-lg-6 col-md-6 col-sm-12>\n      <h3>Invite members</h3>\n      <ion-item>\n        <ion-label floating>Identifier <ion-spinner *ngIf="inviteBusy"></ion-spinner></ion-label>\n        <ion-input type="text" [(ngModel)]="memberIdentifier"></ion-input>\n      </ion-item>\n      <ion-item>\n        <button ion-button large secondary (click)="addOrganizationMember()" [disabled]="!memberIdentifier || inviteBusy">\n          Add organization member&nbsp;<ion-icon name="create"></ion-icon>\n        </button>\n      </ion-item>\n    </ion-col>\n    <ion-col col-lg-6 col-md-6 col-sm-12 *ngIf="invites">\n      <h3>Invites</h3>\n      <ion-list *ngFor="let invite of invites">\n        <ion-item ion-item>\n          <ion-icon name="person" item-start [color]="\'dark\'"></ion-icon>\n          {{invite.user.username}}\n        </ion-item>\n        <ion-item>\n          <ion-label floating>Invite code</ion-label>\n          <ion-input type="text" [value]="invite.skylink"></ion-input>\n        </ion-item>\n      </ion-list>\n    </ion-col>\n  </ion-row>\n  <ion-row *ngIf="settingsService.remoteSettings.restricted && bulletinSecretService.identity.type === \'organization\'">\n    <ion-col col-lg-6 col-md-6 col-sm-12>\n      <h3>Admin</h3>\n      <ion-item>\n        <button ion-button large secondary (click)="signInToDashboard()">\n          Sign-in to Dashboard&nbsp;<ion-icon name="create"></ion-icon>\n        </button>\n      </ion-item>\n    </ion-col>\n  </ion-row>\n  <ion-row *ngIf="settingsService.remoteSettings.restricted && bulletinSecretService.identity.type === \'organization_member\'">\n    <ion-col col-lg-6 col-md-6 col-sm-12>\n      <h3>Invite contacts</h3>\n      <ion-item>\n        <ion-label floating>Identifier <ion-spinner *ngIf="inviteBusy"></ion-spinner></ion-label>\n        <ion-input type="text" [(ngModel)]="contactIdentifier"></ion-input>\n      </ion-item>\n      <ion-item>\n        <button ion-button large secondary (click)="addMemberContact()" [disabled]="!contactIdentifier || inviteBusy">\n          Add contact&nbsp;<ion-icon name="create"></ion-icon>\n        </button>\n      </ion-item>\n    </ion-col>\n    <ion-col col-lg-6 col-md-6 col-sm-12 *ngIf="invites">\n      <h3>Invites</h3>\n      <ion-list *ngFor="let invite of invites">\n        <ion-item ion-item>\n          <ion-icon name="person" item-start [color]="\'dark\'"></ion-icon>\n          {{invite.user.username}}\n        </ion-item>\n        <ion-item>\n          <ion-label floating>Invite code</ion-label>\n          <ion-input type="text" [value]="invite.skylink"></ion-input>\n        </ion-item>\n      </ion-list>\n    </ion-col>\n  </ion-row>\n</ion-content>\n'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/home/home.html"*/
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

/***/ 226:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return PeerService; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__ionic_storage__ = __webpack_require__(48);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__angular_http__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3_rxjs_operators__ = __webpack_require__(52);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__bulletinSecret_service__ = __webpack_require__(14);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__transaction_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__settings_service__ = __webpack_require__(10);
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
                "websocketUrl": domain + "/websocket",
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
                for (var i = 0; i < Object.keys(remoteSettings).length; i++) {
                    try {
                        var url = new URL(remoteSettings[Object.keys(remoteSettings)[i]]);
                        remoteSettings[Object.keys(remoteSettings)[i]] = url.protocol + '//' + location.host + (url.pathname === '/' ? '' : url.pathname);
                    }
                    catch (e) {
                        continue;
                    }
                }
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

/***/ 227:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return ChatPage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(5);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__ionic_storage__ = __webpack_require__(48);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_graph_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_bulletinSecret_service__ = __webpack_require__(14);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_transaction_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__app_settings_service__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__list_list__ = __webpack_require__(69);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__profile_profile__ = __webpack_require__(70);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_10__angular_http__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_11__app_websocket_service__ = __webpack_require__(37);
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
    function ChatPage(navCtrl, navParams, storage, walletService, transactionService, alertCtrl, graphService, loadingCtrl, bulletinSecretService, settingsService, ahttp, toastCtrl, events, websocketService) {
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
        this.events = events;
        this.websocketService = websocketService;
        this.identity = this.navParams.get('identity');
        this.label = this.identity.username;
        var identity = JSON.parse(JSON.stringify(this.graphService.toIdentity(this.identity))); //deep copy
        if (this.graphService.isGroup(identity)) {
            identity.collection = this.settingsService.collections.GROUP_CHAT;
        }
        else {
            identity.collection = this.settingsService.collections.CHAT;
        }
        var rids = this.graphService.generateRids(identity);
        this.rid = rids.rid;
        this.requested_rid = rids.requested_rid;
        this.requester_rid = rids.requester_rid;
        this.storage.get('blockchainAddress').then(function (blockchainAddress) {
            _this.blockchainAddress = blockchainAddress;
        });
        this.refresh(null, true);
        this.events.subscribe('newchat', function () {
            _this.navCtrl.getActive().component.name === 'ChatPage' && _this.refresh(null);
        });
    }
    ChatPage.prototype.setRecipient = function (identity) {
        this.recipient = identity;
    };
    ChatPage.prototype.removeRecipient = function () {
        this.recipient = undefined;
    };
    ChatPage.prototype.parseChats = function () {
        var group = this.graphService.isGroup(this.identity);
        var rid = group ? this.requested_rid : this.rid;
        if (this.graphService.graph.messages[rid]) {
            this.chats = this.graphService.graph.messages[rid];
            this.graphService.sortInt(this.chats, 'time', true);
            for (var i = 0; i < this.chats.length; i++) {
                if (!group) {
                    this.chats[i].relationship.identity = (this.chats[i].public_key === this.bulletinSecretService.identity.public_key ?
                        this.bulletinSecretService.identity :
                        this.graphService.getIdentityFromTxn(this.graphService.friends_indexed[rid], this.settingsService.collections.CONTACT));
                }
                var datetime = new Date(parseInt(this.chats[i].time) * 1000);
                this.chats[i].time = datetime.toLocaleDateString() + ' ' + datetime.toLocaleTimeString();
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
        var collection;
        if (this.graphService.isGroup(this.identity)) {
            collection = this.settingsService.collections.GROUP_CHAT;
        }
        else {
            collection = this.settingsService.collections.CHAT;
        }
        return this.graphService.getMessages([this.graphService.groups_indexed[this.requested_rid] ? this.requested_rid : this.rid], collection, true)
            .then(function () {
            _this.loading = false;
            if (refresher)
                refresher.complete();
            return _this.parseChats();
        })
            .then(function () {
            setTimeout(function () {
                _this.content && _this.content.scrollToBottom(400);
                _this.input.setFocus();
            }, 500);
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
        var identity = item.relationship.identity;
        var rid = this.graphService.generateRid(identity.username_signature, this.bulletinSecretService.identity.username_signature);
        var cached_identity = this.graphService.friends_indexed[rid];
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_9__profile_profile__["a" /* ProfilePage */], {
            identity: this.graphService.getIdentityFromTxn(cached_identity) || identity
        });
    };
    ChatPage.prototype.send = function () {
        if (this.busy || (!this.chatText && !this.recipient && !this.amount))
            return;
        this.busy = true;
        return this.sendMessagePromise();
    };
    ChatPage.prototype.sendMessagePromise = function () {
        var _this = this;
        return this.walletService.get(this.amount || 0)
            .then(function () {
            if (_this.graphService.isGroup(_this.identity)) {
                var group = _this.graphService.getIdentityFromTxn(_this.graphService.groups_indexed[_this.requested_rid], _this.settingsService.collections.GROUP);
                var info = {
                    relationship: {
                        identity: _this.bulletinSecretService.identity,
                        skylink: _this.skylink,
                        filename: _this.filepath
                    },
                    rid: _this.rid,
                    requester_rid: _this.requester_rid,
                    requested_rid: _this.requested_rid,
                    group: true,
                    shared_secret: group.username_signature,
                    outputs: []
                };
                if (_this.recipient && _this.amount) {
                    info.to = _this.bulletinSecretService.publicKeyToAddress(_this.recipient.public_key);
                    info.value = _this.amount;
                    info.relationship.recipient = _this.recipient;
                }
                info.relationship[_this.settingsService.collections.GROUP_CHAT] = _this.recipient && _this.amount ? 'Sent ' + _this.amount + ' YDA to ' + _this.recipient.username : _this.chatText;
                ;
                return _this.transactionService.generateTransaction(info);
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
                    var info = {
                        dh_public_key: dh_public_key,
                        dh_private_key: dh_private_key,
                        relationship: {
                            skylink: _this.skylink,
                            filename: _this.filepath
                        },
                        shared_secret: shared_secret,
                        rid: _this.rid,
                        requester_rid: _this.requester_rid,
                        requested_rid: _this.requested_rid,
                        outputs: []
                    };
                    if (_this.recipient && _this.amount) {
                        info.to = _this.bulletinSecretService.publicKeyToAddress(_this.recipient.public_key);
                        info.value = _this.amount;
                        info.relationship.recipient = _this.recipient;
                    }
                    info.relationship[_this.settingsService.collections.CHAT] = _this.recipient && _this.amount ? 'Sent ' + _this.amount + ' YDA to ' + _this.recipient.username : _this.chatText;
                    return _this.transactionService.generateTransaction(info);
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
            _this.busy = false;
            _this.chatText = '';
            _this.skylink = null;
            _this.filedata = null;
            _this.filepath = null;
            _this.recipient = null;
            _this.amount = 0;
            _this.refresh(null);
        })
            .catch(function (err) {
            _this.busy = false;
            console.log(err);
            var alert = _this.alertCtrl.create();
            alert.setTitle('Message error');
            alert.setSubTitle(err);
            alert.addButton('Ok');
            alert.present();
        });
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
            selector: 'page-chat',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/chat/chat.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n    <ion-title>{{label}}</ion-title>\n  </ion-navbar>\n</ion-header>\n<ion-content #content>\n  <ion-refresher (ionRefresh)="refresh($event)">\n    <ion-refresher-content></ion-refresher-content>\n  </ion-refresher>\n  <ion-spinner *ngIf="loading"></ion-spinner>\n  <ion-list>\n    <ion-item *ngFor="let item of chats" text-wrap>\n        <strong>\n          <span ion-text style="font-size: 20px;" (click)="viewProfile(item)">{{item.relationship.identity ? item.relationship.identity.username : \'Anonymous\'}}</span>\n        </strong>\n        <span style="font-size: 10px; color: rgb(88, 88, 88);" ion-text>{{item.time}}</span>\n        <h3 *ngIf="!item.relationship.isInvite && item.relationship[settingsService.collections.CHAT]">{{item.relationship[settingsService.collections.CHAT]}}</h3>\n        <h3 *ngIf="!item.relationship.isInvite && item.relationship[settingsService.collections.GROUP_CHAT]">{{item.relationship[settingsService.collections.GROUP_CHAT]}}</h3>\n        <button *ngIf="!graphService.isMe(item.relationship.identity) && !settingsService.remoteSettings.restricted" ion-button small secondary title="Send Yada Coins!" (click)="setRecipient(item.relationship.identity)" class="coin-button">\n          <ion-icon name="cash"></ion-icon>\n        </button>\n        <h3 *ngIf="item.relationship.isInvite && item.relationship[settingsService.collections.CHAT].group === true">Invite to join {{item.relationship[settingsService.collections.CHAT].username}}</h3>\n        <button *ngIf="item.relationship.isInvite && item.relationship[settingsService.collections.CHAT].group === true" ion-button (click)="joinGroup(item)">Join group</button>\n        <button *ngIf="item.relationship.isInvite && item.relationship[settingsService.collections.CHAT].group !== true" ion-button (click)="requestFriend(item)">Join group</button>\n        <a href="https://centeridentity.com/sia-download?skylink={{item.relationship.skylink}}" target="_blank" *ngIf="item.relationship.skylink">Download {{item.relationship.filename}}</a>\n        <hr />\n    </ion-item>\n  </ion-list>\n</ion-content>\n<ion-footer>\n  <ion-item *ngIf="recipient" title="Verified" class="sender">{{recipient.username}} <ion-icon *ngIf="graphService.isAdded(recipient)" name="checkmark-circle" class="success"></ion-icon> <ion-icon name="close-circle" class="grey" (click)="removeRecipient()"></ion-icon></ion-item>\n  <ion-item *ngIf="recipient">\n    <ion-label color="primary" fixed>Amount</ion-label>\n    <ion-input type="number" placeholder="Enter an amount" [(ngModel)]="amount"></ion-input>\n  </ion-item>\n  <ion-item *ngIf="!recipient">\n    <ion-label floating>Chat text</ion-label>\n    <ion-input [(ngModel)]="chatText" (keyup.enter)="send()" #input></ion-input>\n  </ion-item>\n  <button *ngIf="!recipient" ion-button (click)="send()" [disabled]="busy && !chatText">Send <ion-spinner *ngIf="busy"></ion-spinner></button>\n  <button *ngIf="recipient" ion-button (click)="send()" [disabled]="busy && !chatText">Send Coins<ion-spinner *ngIf="busy"></ion-spinner></button>\n  <ion-input type="file" (change)="changeListener($event)" *ngIf="settingsService.remoteSettings.restricted"></ion-input>\n</ion-footer>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/chat/chat.html"*/,
            queries: {
                content: new __WEBPACK_IMPORTED_MODULE_0__angular_core__["_14" /* ViewChild */]('content'),
                input: new __WEBPACK_IMPORTED_MODULE_0__angular_core__["_14" /* ViewChild */]('input')
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
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["l" /* ToastController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["b" /* Events */],
            __WEBPACK_IMPORTED_MODULE_11__app_websocket_service__["a" /* WebSocketService */]])
    ], ChatPage);
    return ChatPage;
}());

//# sourceMappingURL=chat.js.map

/***/ }),

/***/ 228:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return SendReceive; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(5);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__app_wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_transaction_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_bulletinSecret_service__ = __webpack_require__(14);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__ionic_native_qr_scanner__ = __webpack_require__(397);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_settings_service__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__ionic_native_social_sharing__ = __webpack_require__(108);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__list_list__ = __webpack_require__(69);
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
    function SendReceive(navCtrl, navParams, qrScanner, transactionService, alertCtrl, bulletinSecretService, walletService, socialSharing, loadingCtrl, ahttp, settingsService) {
        this.navCtrl = navCtrl;
        this.navParams = navParams;
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
        if (this.navParams.get('identity')) {
            this.identity = this.navParams.get('identity');
            this.address = this.bulletinSecretService.publicKeyToAddress(this.identity.public_key);
        }
        this.recipients = [
            {
                address: '',
                value: 0
            }
        ];
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
    SendReceive.prototype.addRecipient = function () {
        this.recipients.push({
            address: '',
            value: 0
        });
    };
    SendReceive.prototype.removeRecipient = function (index) {
        this.recipients.splice(index, 1);
    };
    SendReceive.prototype.submit = function () {
        var _this = this;
        var value = parseFloat(this.value);
        var total = value + 0.01;
        var alert = this.alertCtrl.create();
        if (!this.recipients[0].to) {
            alert.setTitle('Enter an address');
            alert.addButton('Ok');
            alert.present();
            return;
        }
        if (!this.recipients[0].value) {
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
                var value_needed = 0;
                _this.recipients.map(function (output) {
                    value_needed += output.value;
                });
                _this.walletService.get(value_needed)
                    .then(function () {
                    if (_this.walletService.wallet.balance < value_needed) {
                        var title = 'Insufficient Funds';
                        var message = "Not enough YadaCoins for transaction.";
                        var alert = _this.alertCtrl.create();
                        alert.setTitle(title);
                        alert.setSubTitle(message);
                        alert.addButton('Ok');
                        alert.present();
                        _this.value = '0';
                        _this.address = '';
                        _this.refresh();
                        _this.loadingModal.dismiss().catch(function () { });
                        throw ('insufficient funds');
                    }
                    return _this.transactionService.generateTransaction({
                        outputs: _this.recipients
                    });
                }).then(function (txn) {
                    return _this.transactionService.sendTransaction(txn);
                }).then(function (txn) {
                    var title = 'Transaction Sent';
                    var message = 'Your transaction has been sent succefully.';
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
    SendReceive.prototype.getSentHistory = function (public_key) {
        var _this = this;
        if (public_key === void 0) { public_key = null; }
        return new Promise(function (resolve, reject) {
            _this.sentLoading = true;
            var options = new __WEBPACK_IMPORTED_MODULE_9__angular_http__["d" /* RequestOptions */]({ withCredentials: true });
            _this.ahttp.get(_this.settingsService.remoteSettings['baseUrl'] + '/get-past-sent-txns?page=' + _this.sentPage + '&public_key=' + (public_key || _this.bulletinSecretService.key.getPublicKeyBuffer().toString('hex')) + '&origin=' + encodeURIComponent(window.location.origin), options)
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
            selector: 'page-sendreceive',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/sendreceive/sendreceive.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n  </ion-navbar>\n</ion-header>\n<ion-content padding>\n  <ion-refresher (ionRefresh)="refresh($event)">\n    <ion-refresher-content></ion-refresher-content>\n  </ion-refresher>\n  <h4>Balance</h4>\n  <ion-item>\n    {{walletService.wallet.balance}} YADA\n  </ion-item>\n  <h4>Pending Balance</h4><ion-note>(including funds to be returned to you from your transactions)</ion-note>\n  <ion-item>\n    {{walletService.wallet.pending_balance}} YADA\n  </ion-item>\n  <h4>Send YadaCoins</h4>\n  <button *ngIf="isDevice" ion-button color="secondary" (click)="scan()" full>Scan Address</button>\n  <ion-item *ngIf="identity" title="Verified" class="sender">Recipient: {{identity.username}} <ion-icon *ngIf="graphService.isAdded(identity)" name="checkmark-circle" class="success"></ion-icon></ion-item>\n  <ion-list>\n    <ion-row *ngFor="let recipient of recipients; let i = index">\n      <ion-col>\n        <ion-item>\n          <ion-label color="primary" stacked>Address</ion-label>\n          <ion-input type="text" placeholder="Recipient address..." [(ngModel)]="recipients[i].to">\n          </ion-input>\n        </ion-item>\n        <ion-item>\n          <ion-label color="primary" fixed>Amount</ion-label>\n          <ion-input type="number" placeholder="Amount..." [(ngModel)]="recipients[i].value"></ion-input>\n        </ion-item>\n      </ion-col>\n      <ion-col>\n        <button ion-button secondary (click)="removeRecipient(i)" *ngIf="i > 0"><ion-icon name="trash"></ion-icon></button>\n      </ion-col>\n    </ion-row>\n  </ion-list>\n  <button ion-button secondary (click)="addRecipient()"><ion-icon name="add"></ion-icon>&nbsp;Add recipient</button>\n  <button ion-button secondary (click)="submit()">Send&nbsp;<ion-icon name="send"></ion-icon></button>\n  <h4>Receive YadaCoins</h4>\n  <ion-item>\n    <ion-label color="primary" stacked>Your Address:</ion-label>\n    <ion-input type="text" [(ngModel)]="createdCode"></ion-input>\n  </ion-item>\n  <button *ngIf="isDevice" ion-button outline item-end (click)="shareAddress()">share address&nbsp;<ion-icon name="share"></ion-icon></button>\n  <ion-card>\n    <ion-card-content>\n      <ngx-qrcode [qrc-value]="createdCode"></ngx-qrcode>\n    </ion-card-content>\n  </ion-card>\n  <h4>Pending Transactions</h4>\n  <strong>Received</strong><br>\n  <button ion-button small (click)="prevReceivedPendingPage()" [disabled]="receivedPendingPage <= 1">< Prev</button> <button ion-button small (click)="nextReceivedPendingPage()" [disabled]="past_received_pending_transactions.length === 0 || past_received_pending_transactions.length < 10">Next ></button>\n  <p *ngIf="past_received_pending_transactions.length === 0">No more results</p><span *ngIf="receivedPendingLoading"> (loading...)</span>\n  <ion-list>\n    <ion-item *ngFor="let txn of past_received_pending_transactions">\n      <ion-label>{{convertDateTime(txn.time)}}</ion-label>\n      <ion-label><a href="https://yadacoin.io/explorer?term={{txn.id}}" target="_blank">{{txn.id}}</a></ion-label>\n      <ion-label>{{txn.value}}</ion-label>\n    </ion-item>\n  </ion-list>\n  <strong>Sent</strong><br>\n  <button ion-button small (click)="prevSentPendingPage()" [disabled]="sentPendingPage <= 1">< Prev</button> <button ion-button small (click)="nextSentPendingPage()" [disabled]="past_sent_pending_transactions.length === 0 || past_sent_pending_transactions.length < 10">Next ></button>\n  <p *ngIf="past_sent_pending_transactions.length === 0">No more results</p><span *ngIf="sentPendingLoading"> (loading...)</span>\n  <ion-list>\n    <ion-item *ngFor="let txn of past_sent_pending_transactions">\n      <ion-label>{{convertDateTime(txn.time)}}</ion-label>\n      <ion-label><a href="https://yadacoin.io/explorer?term={{txn.id}}" target="_blank">{{txn.id}}</a></ion-label>\n      <ion-label>{{txn.value}}</ion-label>\n    </ion-item>\n  </ion-list>\n  <h4>Transaction history</h4>\n  <strong>Received</strong><br>\n  <button ion-button small (click)="prevReceivedPage()" [disabled]="receivedPage <= 1">< Prev</button> <button ion-button small (click)="nextReceivedPage()" [disabled]="past_received_transactions.length === 0 || past_received_transactions.length < 10">Next ></button>\n  <p *ngIf="past_received_transactions.length === 0">No more results</p><span *ngIf="receivedLoading"> (loading...)</span>\n  <ion-list>\n    <ion-item *ngFor="let txn of past_received_transactions">\n      <ion-label>{{convertDateTime(txn.time)}}</ion-label>\n      <ion-label><a href="https://yadacoin.io/explorer?term={{txn.id}}" target="_blank">{{txn.id}}</a></ion-label>\n      <ion-label>{{txn.value}}</ion-label>\n    </ion-item>\n  </ion-list>\n  <strong>Sent</strong><br>\n  <button ion-button small (click)="prevSentPage()" [disabled]="sentPage <= 1">< Prev</button> <button ion-button small (click)="nextSentPage()" [disabled]="past_sent_transactions.length === 0 || past_sent_transactions.length < 10">Next ></button>\n  <p *ngIf="past_sent_transactions.length === 0">No more results</p><span *ngIf="sentLoading"> (loading...)</span>\n  <ion-list>\n    <ion-item *ngFor="let txn of past_sent_transactions">\n      <ion-label>{{convertDateTime(txn.time)}}</ion-label>\n      <ion-label><a href="https://yadacoin.io/explorer?term={{txn.id}}" target="_blank">{{txn.id}}</a></ion-label>\n      <ion-label>{{txn.value}}</ion-label>\n    </ion-item>\n  </ion-list>\n</ion-content>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/sendreceive/sendreceive.html"*/
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["i" /* NavController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["j" /* NavParams */],
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

/***/ 229:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return CalendarPage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(5);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__app_bulletinSecret_service__ = __webpack_require__(14);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_graph_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_settings_service__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__mail_compose__ = __webpack_require__(109);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__mail_mailitem__ = __webpack_require__(138);
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
    function CalendarPage(navCtrl, graphService, bulletinSecretService, settingsService) {
        this.navCtrl = navCtrl;
        this.graphService = graphService;
        this.bulletinSecretService = bulletinSecretService;
        this.settingsService = settingsService;
        this.getCalendar({});
    }
    CalendarPage.prototype.addZeros = function (date) {
        return ('00' + date).substr(-2, 2);
    };
    CalendarPage.prototype.ionViewDidEnter = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            _this.loading = true;
            var rids = [_this.graphService.generateRid(_this.bulletinSecretService.identity.username_signature, _this.bulletinSecretService.identity.username_signature, _this.settingsService.collections.CALENDAR)];
            var group_rids = [];
            for (var i = 0; i < _this.graphService.graph.groups.length; i++) {
                var group = _this.graphService.getIdentityFromTxn(_this.graphService.graph.groups[i], _this.settingsService.collections.GROUP);
                group_rids.push(_this.graphService.generateRid(group.username_signature, group.username_signature, _this.settingsService.collections.CALENDAR));
                group_rids.push(_this.graphService.generateRid(group.username_signature, group.username_signature, _this.settingsService.collections.GROUP_CALENDAR));
            }
            var file_rids = [];
            for (var i = 0; i < _this.graphService.graph.files.length; i++) {
                var file = _this.graphService.getIdentityFromTxn(_this.graphService.graph.files[i]);
                file_rids.push(_this.graphService.generateRid(file.username_signature, file.username_signature, _this.settingsService.collections.CALENDAR));
                file_rids.push(_this.graphService.generateRid(file.username_signature, file.username_signature, _this.settingsService.collections.GROUP_CALENDAR));
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
                var group = _this.graphService.getIdentityFromTxn(_this.graphService.groups_indexed[txn.requested_rid], _this.settingsService.collections.GROUP);
                var event = txn.relationship[_this.settingsService.collections.CALENDAR] ||
                    txn.relationship[_this.settingsService.collections.GROUP_CALENDAR];
                var eventDate = event.event_datetime;
                var index = eventDate.getFullYear() + _this.addZeros(eventDate.getMonth()) + _this.addZeros(eventDate.getDate());
                if (!events[index]) {
                    events[index] = [];
                }
                var altSender = _this.graphService.getIdentityFromTxn(_this.graphService.friends_indexed[txn.rid], _this.settingsService.collections.CONTACT);
                events[index].push({
                    group: group || null,
                    sender: event.sender || altSender,
                    subject: event.subject,
                    body: event.body,
                    datetime: new Date(parseInt(txn.time) * 1000).toISOString().slice(0, 19).replace('T', ' '),
                    id: txn.id,
                    message_type: event.message_type,
                    event_datetime: event.event_datetime
                });
            });
            _this.getCalendar(events);
            _this.loading = false;
        });
    };
    CalendarPage.prototype.itemTapped = function (event, item) {
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_6__mail_mailitem__["a" /* MailItemPage */], {
            item: item
        });
    };
    CalendarPage.prototype.createEvent = function (event, item) {
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_5__mail_compose__["a" /* ComposePage */], {
            item: {
                message_type: 'calendar'
            }
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
            if (calDate.getFullYear() > year)
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
            selector: 'page-calendar',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/calendar/calendar.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n  </ion-navbar>\n</ion-header>\n<ion-content padding>\n  <button ion-button secondary (click)="createEvent()">Create new event</button>\n  <ion-spinner *ngIf="loading"></ion-spinner>\n  <table width="100%" height="100%" *ngIf="calendar">\n    <tr>\n      <th width="12.5%"></th>\n      <th width="12.5%">Sunday</th>\n      <th width="12.5%">Monday</th>\n      <th width="12.5%">Tuesday</th>\n      <th width="12.5%">Wednesday</th>\n      <th width="12.5%">Thursday</th>\n      <th width="12.5%">Friday</th>\n      <th width="12.5%">Saturday</th>\n    </tr>\n    <tr *ngFor="let row of calendar.rows">\n      <td *ngFor="let day of row.days">\n        <div *ngIf="day.date">{{day.date.getDate()}}</div>\n        <div *ngIf="day.events">\n          <div *ngFor="let event of day.events">\n            <div (click)="itemTapped($event, event)">{{event.subject}}</div>\n          </div>\n        </div>\n      </td>\n    </tr>\n  </table>\n</ion-content>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/calendar/calendar.html"*/
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["i" /* NavController */],
            __WEBPACK_IMPORTED_MODULE_3__app_graph_service__["a" /* GraphService */],
            __WEBPACK_IMPORTED_MODULE_2__app_bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_4__app_settings_service__["a" /* SettingsService */]])
    ], CalendarPage);
    return CalendarPage;
}());

//# sourceMappingURL=calendar.js.map

/***/ }),

/***/ 230:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return AssetsPage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(5);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__app_bulletinSecret_service__ = __webpack_require__(14);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_graph_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_settings_service__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__createasset__ = __webpack_require__(400);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__assetitem__ = __webpack_require__(401);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};







var AssetsPage = /** @class */ (function () {
    function AssetsPage(navCtrl, navParams, graphService, bulletinSecretService, settingsService, events) {
        this.navCtrl = navCtrl;
        this.navParams = navParams;
        this.graphService = graphService;
        this.bulletinSecretService = bulletinSecretService;
        this.settingsService = settingsService;
        this.events = events;
        this.items = [];
        this.loading = false;
        this.loading = true;
        var rids = [this.graphService.generateRid(this.bulletinSecretService.identity.username_signature, this.bulletinSecretService.identity.username_signature, this.settingsService.collections.ASSET)];
        this.rids = rids;
    }
    AssetsPage.prototype.ionViewDidEnter = function () {
        this.refresh();
    };
    AssetsPage.prototype.refresh = function () {
        var _this = this;
        return this.graphService.getAssets(this.rids)
            .then(function (items) {
            _this.loading = false;
            _this.items = items.filter(function (item) {
                try {
                    return item.relationship[_this.settingsService.collections.ASSET].data.substr(0, 5) === 'data:';
                }
                catch (err) {
                    return false;
                }
            });
        });
    };
    AssetsPage.prototype.itemTapped = function (event, item) {
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_6__assetitem__["a" /* AssetItemPage */], {
            item: item
        });
    };
    AssetsPage.prototype.createAsset = function () {
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_5__createasset__["a" /* CreateAssetPage */]);
    };
    AssetsPage = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["n" /* Component */])({
            selector: 'assets',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/assets/assets.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n  </ion-navbar>\n</ion-header>\n<ion-content padding>\n  <ion-refresher (ionRefresh)="refresh($event)">\n    <ion-refresher-content></ion-refresher-content>\n  </ion-refresher>\n  <ion-spinner *ngIf="loading"></ion-spinner>\n  <button ion-button secondary (click)="createAsset($event)">Create asset</button>\n  <ion-card *ngIf="items && items.length == 0">\n      <ion-card-content>\n        <ion-card-title style="text-overflow:ellipsis;" text-wrap>\n          No items to display.\n      </ion-card-title>\n    </ion-card-content>\n  </ion-card>\n  <ion-row>\n    <ion-col col-md-3>\n      <ion-card ion-item *ngFor="let item of items" (click)="itemTapped($event, item)" style="cursor: pointer;">\n        <ion-card-title style="text-overflow:ellipsis;" text-wrap>\n          <img [src]="item.relationship[settingsService.collections.ASSET].data">\n        </ion-card-title>\n        <ion-card-content>\n          {{item.relationship[settingsService.collections.ASSET].identity.username}}\n        </ion-card-content>\n      </ion-card>\n    </ion-col>\n  </ion-row>\n</ion-content>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/assets/assets.html"*/
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["i" /* NavController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["j" /* NavParams */],
            __WEBPACK_IMPORTED_MODULE_3__app_graph_service__["a" /* GraphService */],
            __WEBPACK_IMPORTED_MODULE_2__app_bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_4__app_settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["b" /* Events */]])
    ], AssetsPage);
    return AssetsPage;
}());

//# sourceMappingURL=assets.js.map

/***/ }),

/***/ 231:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return FirebaseService; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__ionic_native_firebase__ = __webpack_require__(404);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__graph_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__settings_service__ = __webpack_require__(10);
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

/***/ 232:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return MailPage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(5);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__app_bulletinSecret_service__ = __webpack_require__(14);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_graph_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_settings_service__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__compose__ = __webpack_require__(109);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__mailitem__ = __webpack_require__(138);
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
    function MailPage(navCtrl, navParams, graphService, bulletinSecretService, settingsService, events) {
        var _this = this;
        this.navCtrl = navCtrl;
        this.navParams = navParams;
        this.graphService = graphService;
        this.bulletinSecretService = bulletinSecretService;
        this.settingsService = settingsService;
        this.events = events;
        this.items = [];
        this.loading = false;
        this.loading = true;
        var rids = [this.graphService.generateRid(this.bulletinSecretService.identity.username_signature, this.bulletinSecretService.identity.username_signature, this.settingsService.collections.MAIL),
            this.graphService.generateRid(this.bulletinSecretService.identity.username_signature, this.bulletinSecretService.identity.username_signature, this.settingsService.collections.CONTRACT),
            this.graphService.generateRid(this.bulletinSecretService.identity.username_signature, this.bulletinSecretService.identity.username_signature, this.settingsService.collections.CONTRACT_SIGNED),
            this.graphService.generateRid(this.bulletinSecretService.identity.username_signature, this.bulletinSecretService.identity.username_signature, this.settingsService.collections.CALENDAR)];
        var group_rids = [];
        for (var i = 0; i < this.graphService.graph.groups.length; i++) {
            var group = this.graphService.getIdentityFromTxn(this.graphService.graph.groups[i]);
            group_rids.push(this.graphService.generateRid(group.username_signature, group.username_signature, this.settingsService.collections.GROUP_MAIL));
        }
        var file_rids = [];
        for (var i = 0; i < this.graphService.graph.files.length; i++) {
            var group = this.graphService.getIdentityFromTxn(this.graphService.graph.files[i]);
            file_rids.push(this.graphService.generateRid(group.username_signature, group.username_signature, this.settingsService.collections.GROUP_MAIL));
        }
        if (group_rids.length > 0) {
            rids = rids.concat(group_rids);
        }
        if (file_rids.length > 0) {
            rids = rids.concat(file_rids);
        }
        this.rids = rids;
        this.events.subscribe('newmail', function () { _this.refresh(); });
        this.refresh();
    }
    MailPage.prototype.refresh = function () {
        var _this = this;
        return this.graphService.getMail(this.rids, this.settingsService.collections.MAIL)
            .then(function () {
            return _this.graphService.getMail(_this.rids, _this.settingsService.collections.GROUP_MAIL);
        })
            .then(function () {
            _this.items = _this.graphService.prepareMailItems(_this.navParams.data.pageTitle.label);
            _this.loading = false;
        });
    };
    MailPage.prototype.itemTapped = function (event, item) {
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_6__mailitem__["a" /* MailItemPage */], {
            item: item
        });
    };
    MailPage.prototype.composeMail = function () {
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_5__compose__["a" /* ComposePage */]);
    };
    MailPage = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["n" /* Component */])({
            selector: 'mail-profile',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/mail/mail.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n  </ion-navbar>\n</ion-header>\n<ion-content padding>\n  <ion-refresher (ionRefresh)="refresh($event)">\n    <ion-refresher-content></ion-refresher-content>\n  </ion-refresher>\n  <button ion-button secondary (click)="composeMail()">Compose</button>\n  <ion-spinner *ngIf="loading"></ion-spinner>\n  <ion-card *ngIf="items && items.length == 0">\n      <ion-card-content>\n        <ion-card-title style="text-overflow:ellipsis;" text-wrap>\n          No items to display.\n      </ion-card-title>\n    </ion-card-content>\n  </ion-card>\n  <ion-list>\n    <button ion-item *ngFor="let item of items" (click)="itemTapped($event, item)">\n      <ion-item>\n        <div title="Verified" class="sender">\n          <span>{{item.sender.username}} <ion-icon *ngIf="graphService.isAdded(item.sender)" name="checkmark-circle" class="success"></ion-icon></span>\n          <span *ngIf="item.group">{{item.group.username}} <ion-icon *ngIf="graphService.isAdded(item.group)" name="checkmark-circle" class="success"></ion-icon></span>\n        </div>\n        <div class="subject">{{item.subject}}</div>\n        <div class="datetime">{{item.datetime}}</div>\n        <div class="body">{{item.body}}</div>\n      </ion-item>\n    </button>\n  </ion-list>\n</ion-content>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/mail/mail.html"*/
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["i" /* NavController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["j" /* NavParams */],
            __WEBPACK_IMPORTED_MODULE_3__app_graph_service__["a" /* GraphService */],
            __WEBPACK_IMPORTED_MODULE_2__app_bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_4__app_settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["b" /* Events */]])
    ], MailPage);
    return MailPage;
}());

//# sourceMappingURL=mail.js.map

/***/ }),

/***/ 233:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return WebPage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(5);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__app_graph_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_bulletinSecret_service__ = __webpack_require__(14);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_settings_service__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_websocket_service__ = __webpack_require__(37);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__angular_forms__ = __webpack_require__(30);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__app_autocomplete_provider__ = __webpack_require__(110);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};








var WebPage = /** @class */ (function () {
    function WebPage(navCtrl, navParams, graphService, bulletinSecretService, settingsService, websocketService, completeTestService) {
        this.navCtrl = navCtrl;
        this.navParams = navParams;
        this.graphService = graphService;
        this.bulletinSecretService = bulletinSecretService;
        this.settingsService = settingsService;
        this.websocketService = websocketService;
        this.completeTestService = completeTestService;
        this.myForm = new __WEBPACK_IMPORTED_MODULE_6__angular_forms__["b" /* FormGroup */]({
            searchTerm: new __WEBPACK_IMPORTED_MODULE_6__angular_forms__["a" /* FormControl */]('', [__WEBPACK_IMPORTED_MODULE_6__angular_forms__["g" /* Validators */].required])
        });
        this.recipient = this.navParams.get('recipient');
        this.resource = this.navParams.get('resource');
        this.content = this.navParams.get('content');
    }
    WebPage.prototype.go = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            return _this.websocketService.directMessageRequest(_this.recipient, _this.settingsService.collections.WEB_PAGE_REQUEST, { resource: _this.resource }, resolve);
        })
            .then(function (item) {
            return _this.content = item.relationship[_this.settingsService.collections.WEB_PAGE_RESPONSE].content;
        });
    };
    WebPage.prototype.signIn = function () {
        var _this = this;
        var identity;
        var url;
        var key = foobar.bitcoin.ECPair.makeRandom();
        return new Promise(function (resolve, reject) {
            return _this.websocketService.directMessageRequest(_this.recipient, _this.settingsService.collections.WEB_CHALLENGE_REQUEST, {}, resolve);
        })
            .then(function (item) {
            var username = item.relationship[_this.settingsService.collections.WEB_CHALLENGE_RESPONSE].challenge;
            identity = {
                wif: key.toWIF(),
                username: username,
                username_signature: foobar.base64.fromByteArray(key.sign(foobar.bitcoin.crypto.sha256(username)).toDER()),
                public_key: key.getPublicKeyBuffer().toString('hex')
            };
            url = item.relationship[_this.settingsService.collections.WEB_CHALLENGE_RESPONSE].url;
            return new Promise(function (resolve, reject) {
                return _this.websocketService.directMessageRequest(_this.recipient, _this.settingsService.collections.WEB_SIGNIN_REQUEST, identity, resolve);
            });
        })
            .then(function (identityTxn) {
            if (identity.wif !== identityTxn.relationship[_this.settingsService.collections.WEB_SIGNIN_RESPONSE].wif)
                return;
            if (identity.username !== identityTxn.relationship[_this.settingsService.collections.WEB_SIGNIN_RESPONSE].username)
                return;
            var iframe;
            iframe = document.createElement('iframe');
            iframe.id = 'myFrame';
            var urlObject = new URL(url);
            iframe.src = urlObject.href;
            iframe.style.display = 'none';
            document.body.appendChild(iframe);
            iframe.onload = function () {
                window.frames['myFrame'].contentWindow.postMessage(identity, urlObject.origin);
                window.open(urlObject.href, '_blank');
                iframe.parentNode.removeChild(iframe);
            };
        });
    };
    WebPage = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["n" /* Component */])({
            selector: 'page-web',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/web/web.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n  </ion-navbar>\n</ion-header>\n\n<ion-content padding>\n  <ion-refresher (ionRefresh)="refresh($event)">\n    <ion-refresher-content></ion-refresher-content>\n  </ion-refresher>\n  <h1>Web</h1>\n  <ion-item>Select a contact and enter a resource.</ion-item>\n  <form [formGroup]="myForm" (ngSubmit)="submit()" *ngIf="!recipient">\n    <ion-auto-complete #searchbar [(ngModel)]="recipient" [options]="{ placeholder : \'Recipient\' }" [dataProvider]="completeTestService" formControlName="searchTerm" required></ion-auto-complete>\n  </form>\n  <ion-item *ngIf="recipient" title="Verified" class="sender">{{recipient.username}} <ion-icon *ngIf="graphService.isAdded(recipient)" name="checkmark-circle" class="success"></ion-icon></ion-item>\n  <ion-item>\n    <ion-input type="text" [(ngModel)]="resource"></ion-input>\n  </ion-item>\n  <ion-item>\n    <button ion-button secondary (click)="go()" [disabled]="!recipient">Go</button>\n  </ion-item>\n  <ion-item>\n    <button ion-button secondary (click)="signIn()" [disabled]="!recipient">Sign in</button>\n  </ion-item>\n  <ion-item>\n    {{content}}\n  </ion-item>\n</ion-content>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/web/web.html"*/
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["i" /* NavController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["j" /* NavParams */],
            __WEBPACK_IMPORTED_MODULE_2__app_graph_service__["a" /* GraphService */],
            __WEBPACK_IMPORTED_MODULE_3__app_bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_4__app_settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_5__app_websocket_service__["a" /* WebSocketService */],
            __WEBPACK_IMPORTED_MODULE_7__app_autocomplete_provider__["a" /* CompleteTestService */]])
    ], WebPage);
    return WebPage;
}());

//# sourceMappingURL=web.js.map

/***/ }),

/***/ 234:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return BuildPagePage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(5);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__app_graph_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_bulletinSecret_service__ = __webpack_require__(14);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_settings_service__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_websocket_service__ = __webpack_require__(37);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_transaction_service__ = __webpack_require__(20);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};







var BuildPagePage = /** @class */ (function () {
    function BuildPagePage(navCtrl, navParams, graphService, bulletinSecretService, settingsService, websocketService, transactionService, alertCtrl) {
        this.navCtrl = navCtrl;
        this.navParams = navParams;
        this.graphService = graphService;
        this.bulletinSecretService = bulletinSecretService;
        this.settingsService = settingsService;
        this.websocketService = websocketService;
        this.transactionService = transactionService;
        this.alertCtrl = alertCtrl;
    }
    BuildPagePage.prototype.save = function () {
        var _this = this;
        var alert = this.alertCtrl.create();
        alert.setTitle('Create web page');
        alert.setSubTitle('Are you sure you want to save this page?');
        alert.addButton({
            text: 'Continue editing'
        });
        alert.addButton({
            text: 'Save',
            handler: function (data) {
                _this.resource = '';
                _this.pageText = '';
                var identity = _this.graphService.toIdentity(JSON.parse(_this.bulletinSecretService.identityJson()));
                identity.collection = _this.settingsService.collections.WEB_PAGE;
                var rids = _this.graphService.generateRids(identity);
                _this.websocketService.newtxn({ resource: _this.resource, content: _this.pageText }, rids, _this.settingsService.collections.WEB_PAGE);
            }
        });
        alert.present();
    };
    BuildPagePage = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["n" /* Component */])({
            selector: 'page-buildpage',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/web/buildpage.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n  </ion-navbar>\n</ion-header>\n\n<ion-content padding>\n  <ion-refresher (ionRefresh)="refresh($event)">\n    <ion-refresher-content></ion-refresher-content>\n  </ion-refresher>\n  <h1>Page resource identifier</h1>\n  <ion-item>\n    <ion-input type="text" [(ngModel)]="resource"></ion-input>\n  </ion-item>\n  <h1>Page content</h1>\n  <ion-item>\n    <ion-textarea type="text" [(ngModel)]="pageText"></ion-textarea>\n  </ion-item>\n  <ion-item>\n    <button ion-button secondary (click)="save()" [disabled]="!resource || !pageText">Save</button>\n  </ion-item>\n</ion-content>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/web/buildpage.html"*/
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["i" /* NavController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["j" /* NavParams */],
            __WEBPACK_IMPORTED_MODULE_2__app_graph_service__["a" /* GraphService */],
            __WEBPACK_IMPORTED_MODULE_3__app_bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_4__app_settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_5__app_websocket_service__["a" /* WebSocketService */],
            __WEBPACK_IMPORTED_MODULE_6__app_transaction_service__["a" /* TransactionService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["a" /* AlertController */]])
    ], BuildPagePage);
    return BuildPagePage;
}());

//# sourceMappingURL=buildpage.js.map

/***/ }),

/***/ 25:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return WalletService; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__bulletinSecret_service__ = __webpack_require__(14);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__settings_service__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__angular_http__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4_rxjs_operators__ = __webpack_require__(52);
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
    WalletService.prototype.get = function (amount_needed, address) {
        var _this = this;
        if (amount_needed === void 0) { amount_needed = 0; }
        if (address === void 0) { address = null; }
        return new Promise(function (resolve, reject) {
            if (!_this.settingsService.remoteSettings || !_this.settingsService.remoteSettings['walletUrl'])
                return resolve();
            return _this.walletPromise(amount_needed, address)
                .then(function (wallet) {
                return resolve(wallet);
            })
                .catch(function (err) {
                return reject(err);
            });
        });
    };
    WalletService.prototype.walletPromise = function (amount_needed, address) {
        var _this = this;
        if (amount_needed === void 0) { amount_needed = 0; }
        if (address === void 0) { address = null; }
        return new Promise(function (resolve, reject) {
            if (!_this.settingsService.remoteSettings['walletUrl']) {
                return reject('no wallet url');
            }
            if (_this.bulletinSecretService.username) {
                var headers = new __WEBPACK_IMPORTED_MODULE_3__angular_http__["a" /* Headers */]();
                headers.append('Authorization', 'Bearer ' + _this.settingsService.tokens[_this.bulletinSecretService.keyname]);
                var options = new __WEBPACK_IMPORTED_MODULE_3__angular_http__["d" /* RequestOptions */]({ headers: headers, withCredentials: true });
                return _this.ahttp.get(_this.settingsService.remoteSettings['walletUrl'] + '?amount_needed=' + amount_needed + '&address=' + (address || _this.bulletinSecretService.key.getAddress()) + '&username_signature=' + _this.bulletinSecretService.username_signature + '&origin=' + window.location.origin, options)
                    .pipe(Object(__WEBPACK_IMPORTED_MODULE_4_rxjs_operators__["timeout"])(30000))
                    .subscribe(function (data) { return __awaiter(_this, void 0, void 0, function () {
                    var wallet;
                    return __generator(this, function (_a) {
                        switch (_a.label) {
                            case 0:
                                if (!data['_body']) return [3 /*break*/, 2];
                                return [4 /*yield*/, data.json()];
                            case 1:
                                wallet = _a.sent();
                                if (!address) {
                                    this.walletError = false;
                                    this.wallet = wallet;
                                    this.wallet.balance = parseFloat(this.wallet.balance); //pasefloat
                                    this.wallet.pending_balance = parseFloat(this.wallet.pending_balance); //pasefloat
                                    this.wallet.balancePretty = this.wallet.balance.toFixed(2);
                                    this.wallet.pendingBalancePretty = this.wallet.pending_balance.toFixed(2);
                                }
                                return [2 /*return*/, resolve(wallet)];
                            case 2:
                                this.walletError = true;
                                this.wallet = {};
                                this.wallet.balancePretty = 0;
                                this.wallet.pendingBalancePretty = 0;
                                return [2 /*return*/, reject("no data returned")];
                        }
                    });
                }); }, function (err) {
                    _this.walletError = true;
                    return reject("data or server error");
                });
            }
            else {
                _this.walletError = true;
                return reject("username not set");
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

/***/ 268:
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
webpackEmptyAsyncContext.id = 268;

/***/ }),

/***/ 309:
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
webpackEmptyAsyncContext.id = 309;

/***/ }),

/***/ 37:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return WebSocketService; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__bulletinSecret_service__ = __webpack_require__(14);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__settings_service__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__angular_http__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4_ionic_angular__ = __webpack_require__(5);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__graph_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__transaction_service__ = __webpack_require__(20);
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







var WebSocketService = /** @class */ (function () {
    function WebSocketService(ahttp, bulletinSecretService, settingsService, graphService, transactionService, events) {
        this.ahttp = ahttp;
        this.bulletinSecretService = bulletinSecretService;
        this.settingsService = settingsService;
        this.graphService = graphService;
        this.transactionService = transactionService;
        this.events = events;
    }
    WebSocketService.prototype.init = function () {
        var _this = this;
        if (this.websocket && this.websocket.readyState > 1) {
            this.websocket.close();
        }
        ;
        this.websocket = new WebSocket(this.settingsService.remoteSettings.websocketUrl);
        this.websocket.onopen = this.onOpen.bind(this);
        this.websocket.onmessage = this.onMessage.bind(this);
        this.websocket.onerror = function (err) {
            console.error('Socket encountered error: ', err.message, 'Closing socket');
            _this.websocket.close();
        };
        this.websocket.onclose = function (e) {
            console.log('Socket is closed. Reconnect will be attempted in 1 second.', e.reason);
            setTimeout(function () {
                _this.init();
            }, 1000);
        };
    };
    WebSocketService.prototype.onOpen = function (event) {
        this.connect();
        console.log(event.data);
    };
    WebSocketService.prototype.onMessage = function (event) {
        var _this = this;
        var directMessageResponseCount;
        var directMessageResponseCounts;
        var msg = JSON.parse(event.data);
        console.log(msg);
        switch (msg.method) {
            case 'connect_confirm':
                for (var i = 0; i < this.graphService.graph.groups.length; i++) {
                    var group = this.graphService.getIdentityFromTxn(this.graphService.graph.groups[i], this.settingsService.collections.GROUP);
                    this.joinGroup(group);
                }
                break;
            case 'join_confirmed':
                // const members = msg.result.members;
                // for (let i=0; i < Object.keys(members).length; i++) {
                //   let requested_rid = Object.keys(members)[i];
                //   let group_members = members[requested_rid];
                //   if(!this.graphService.online[requested_rid]) this.graphService.online[requested_rid] = [];
                //   this.graphService.online[requested_rid] = this.graphService.online[requested_rid].concat(group_members)
                // }
                break;
            case 'newtxn':
                if (msg.params.transaction.public_key === this.bulletinSecretService.identity.public_key)
                    return;
                var collection = this.graphService.getNewTxnCollection(msg.params.transaction);
                if (collection) {
                    switch (collection) {
                        case this.settingsService.collections.CONTACT:
                            this.graphService.parseFriendRequests([msg.params.transaction]);
                            this.graphService.refreshFriendsAndGroups()
                                .then(function () {
                                return _this.graphService.addNotification(msg.params.transaction, _this.settingsService.collections.CONTACT);
                            });
                            break;
                        case this.settingsService.collections.CALENDAR:
                            var calendar = this.graphService.parseCalendar([msg.params.transaction]);
                            return this.graphService.addNotification(calendar, this.settingsService.collections.CALENDAR);
                            break;
                        case this.settingsService.collections.GROUP_CALENDAR:
                            var group_calendar = this.graphService.parseCalendar([msg.params.transaction]);
                            return this.graphService.addNotification(group_calendar, this.settingsService.collections.GROUP_CALENDAR);
                            break;
                        case this.settingsService.collections.CHAT:
                            this.graphService.parseMessages([msg.params.transaction], 'new_messages_counts', 'new_messages_count', msg.params.transaction.rid, this.settingsService.collections.CHAT, 'last_message_height')
                                .then(function (item) {
                                if (!_this.graphService.graph.messages[msg.params.transaction.rid]) {
                                    _this.graphService.graph.messages[msg.params.transaction.rid] = [];
                                }
                                _this.graphService.graph.messages[msg.params.transaction.rid].push(item[0]);
                                _this.events.publish('newchat');
                                return _this.graphService.addNotification(item[0], _this.settingsService.collections.CHAT);
                            });
                            break;
                        case this.settingsService.collections.CONTRACT:
                            break;
                        case this.settingsService.collections.CONTRACT_SIGNED:
                            break;
                        case this.settingsService.collections.GROUP_CHAT:
                            this.graphService.parseMessages([msg.params.transaction], 'new_group_messages_counts', 'new_group_messages_count', msg.params.transaction.rid, this.settingsService.collections.GROUP_CHAT, 'last_group_message_height')
                                .then(function (item) {
                                if (!_this.graphService.graph.messages[msg.params.transaction.requested_rid]) {
                                    _this.graphService.graph.messages[msg.params.transaction.requested_rid] = [];
                                }
                                _this.graphService.graph.messages[msg.params.transaction.requested_rid].push(item[0]);
                                _this.events.publish('newchat');
                                return _this.graphService.addNotification(item[0], _this.settingsService.collections.GROUP_CHAT);
                            });
                            break;
                        case this.settingsService.collections.GROUP_MAIL:
                            this.graphService.parseMail([msg.params.transaction], 'new_sent_mail_counts', 'new_sent_mail_count', undefined, this.settingsService.collections.GROUP_MAIL, 'last_sent_mail_height')
                                .then(function (item) {
                                _this.events.publish('newmail');
                                return _this.graphService.addNotification(item, _this.settingsService.collections.GROUP_MAIL);
                            });
                            break;
                        case this.settingsService.collections.MAIL:
                            var mailCount = void 0;
                            var mailCounts = void 0;
                            this.graphService.parseMail([msg.params.transaction], mailCount, mailCounts, msg.params.transaction.rid, this.settingsService.collections.MAIL)
                                .then(function (item) {
                                _this.events.publish('newmail');
                                return _this.graphService.addNotification(item, _this.settingsService.collections.MAIL);
                            });
                            break;
                        case this.settingsService.collections.PERMISSION_REQUEST:
                            break;
                        case this.settingsService.collections.SIGNATURE_REQUEST:
                            var permissionRequestCount = void 0;
                            var permissionRequestCounts = void 0;
                            this.graphService.parseMessages([msg.params.transaction], permissionRequestCount, permissionRequestCounts, msg.params.transaction.rid, this.settingsService.collections.SIGNATURE_REQUEST)
                                .then(function (item) {
                                return _this.graphService.addNotification(item[msg.params.transaction.rid][0], _this.settingsService.collections.SIGNATURE_REQUEST);
                            });
                            break;
                        case this.settingsService.collections.WEB_CHALLENGE_REQUEST:
                            var directMessageRequestCount = void 0;
                            var directMessageRequestCounts = void 0;
                            this.graphService.parseMessages([msg.params.transaction], directMessageRequestCount, directMessageRequestCounts, msg.params.transaction.rid, this.settingsService.collections.WEB_CHALLENGE_REQUEST)
                                .then(function (items) {
                                _this.directMessageResponse(msg.params.transaction.rid, _this.settingsService.collections.WEB_CHALLENGE_RESPONSE, {
                                    challenge: uuid4(),
                                    url: _this.settingsService.remoteSettings.webSignInUrl
                                });
                            });
                            break;
                        case this.settingsService.collections.WEB_CHALLENGE_RESPONSE:
                            this.graphService.parseMessages([msg.params.transaction], directMessageResponseCount, directMessageResponseCounts, msg.params.transaction.rid, this.settingsService.collections.WEB_CHALLENGE_RESPONSE)
                                .then(function (items) {
                                return _this.directMessageRequestResolve(items[msg.params.transaction.rid][0]);
                            });
                            break;
                        case this.settingsService.collections.WEB_SIGNIN_REQUEST:
                            this.graphService.parseMessages([msg.params.transaction], directMessageRequestCount, directMessageRequestCounts, msg.params.transaction.rid, this.settingsService.collections.WEB_SIGNIN_REQUEST)
                                .then(function (items) {
                                _this.directMessageResponse(msg.params.transaction.rid, _this.settingsService.collections.WEB_SIGNIN_RESPONSE, items[msg.params.transaction.rid][0].relationship[_this.settingsService.collections.WEB_SIGNIN_REQUEST]);
                            });
                            break;
                        case this.settingsService.collections.WEB_SIGNIN_RESPONSE:
                            this.graphService.parseMessages([msg.params.transaction], directMessageResponseCount, directMessageResponseCounts, msg.params.transaction.rid, this.settingsService.collections.WEB_SIGNIN_RESPONSE)
                                .then(function (items) {
                                return _this.directMessageRequestResolve(items[msg.params.transaction.rid][0]);
                            });
                            break;
                        case this.settingsService.collections.WEB_PAGE:
                            var webpage = this.graphService.parseMyPages([msg.params.transaction]);
                            this.graphService.addNotification(webpage, this.settingsService.collections.WEB_PAGE);
                            break;
                        case this.settingsService.collections.WEB_PAGE_REQUEST:
                            var webRequestCount = void 0;
                            var webRequestCounts = void 0;
                            this.graphService.parseMessages([msg.params.transaction], webRequestCount, webRequestCounts, msg.params.transaction.rid, this.settingsService.collections.WEB_PAGE_REQUEST)
                                .then(function (items) {
                                var myRids2 = [_this.graphService.generateRid(_this.bulletinSecretService.identity.username_signature, _this.bulletinSecretService.identity.username_signature, _this.settingsService.collections.WEB_PAGE)];
                                return _this.graphService.getMyPages(myRids2);
                            })
                                .then(function (items) {
                                var request = msg.params.transaction;
                                var myPages = _this.graphService.graph.mypages.filter(function (item2) {
                                    return item2.relationship[_this.settingsService.collections.WEB_PAGE].resource === request.relationship[_this.settingsService.collections.WEB_PAGE_REQUEST].resource;
                                });
                                var webResponse;
                                if (myPages[0]) {
                                    webResponse = {
                                        resource: myPages[0].relationship[_this.settingsService.collections.WEB_PAGE].resource,
                                        content: myPages[0].relationship[_this.settingsService.collections.WEB_PAGE].content
                                    };
                                }
                                else {
                                    webResponse = {
                                        resource: request.relationship[_this.settingsService.collections.WEB_PAGE_REQUEST].resource,
                                        content: 'Page not found for resource.'
                                    };
                                }
                                _this.directMessageResponse(msg.params.transaction.rid, _this.settingsService.collections.WEB_PAGE_RESPONSE, webResponse);
                            });
                            break;
                        case this.settingsService.collections.WEB_PAGE_RESPONSE:
                            var webResponseCount = void 0;
                            var webResponseCounts = void 0;
                            this.graphService.parseMessages([msg.params.transaction], webResponseCount, webResponseCounts, msg.params.transaction.rid, this.settingsService.collections.WEB_PAGE_RESPONSE)
                                .then(function (items) {
                                return _this.directMessageRequestResolve(items[msg.params.transaction.rid][0]);
                            });
                            break;
                    }
                }
                break;
            case 'newblock':
                var block = msg.params.payload.block;
                block.height = block.index;
                this.settingsService.latest_block = block;
                break;
        }
    };
    WebSocketService.prototype.connect = function () {
        this.websocket.send(JSON.stringify({
            id: '',
            jsonrpc: 2.0,
            method: 'connect',
            params: {
                identity: this.graphService.toIdentity(this.bulletinSecretService.identity)
            }
        }));
    };
    WebSocketService.prototype.joinGroup = function (identity) {
        return this.websocket.send(JSON.stringify({
            id: '',
            jsonrpc: 2.0,
            method: 'join_group',
            params: identity
        }));
    };
    WebSocketService.prototype.newtxn = function (item, rids, collection, shared_secret, extra_data) {
        var _this = this;
        if (shared_secret === void 0) { shared_secret = null; }
        if (extra_data === void 0) { extra_data = {}; }
        var request = __assign({}, rids, { relationship: {} }, extra_data);
        if (shared_secret) {
            request.shared_secret = shared_secret;
        }
        request.relationship[collection] = item;
        return this.transactionService.generateTransaction(request)
            .then(function (txn) {
            _this.sendnewtxn();
            return txn;
        });
    };
    WebSocketService.prototype.directMessageRequest = function (identity, collection, relationship, resolve) {
        var _this = this;
        this.directMessageRequestResolve = resolve;
        identity.collection = collection;
        var rids = this.graphService.generateRids(identity);
        var dh_public_key = this.graphService.keys[rids.rid].dh_public_keys[0];
        var dh_private_key = this.graphService.keys[rids.rid].dh_private_keys[0];
        var privk = new Uint8Array(dh_private_key.match(/[\da-f]{2}/gi).map(function (h) {
            return parseInt(h, 16);
        }));
        var pubk = new Uint8Array(dh_public_key.match(/[\da-f]{2}/gi).map(function (h) {
            return parseInt(h, 16);
        }));
        var shared_secret = this.toHex(X25519.getSharedKey(privk, pubk));
        var request = __assign({}, rids, { relationship: {}, shared_secret: shared_secret });
        request.relationship[collection] = relationship;
        this.transactionService.generateTransaction(request)
            .then(function () {
            _this.sendnewtxn();
        });
    };
    WebSocketService.prototype.directMessageResponse = function (rid, collection, relationship) {
        var _this = this;
        var myRids = this.graphService.generateRids(this.bulletinSecretService.identity);
        var recipient;
        if (this.graphService.friends_indexed[rid]) {
            recipient = this.graphService.getIdentityFromTxn(this.graphService.friends_indexed[rid], this.settingsService.collections.CONTACT);
        }
        if (myRids.rid == rid) {
            recipient = this.bulletinSecretService.identity;
        }
        if (!recipient)
            return;
        recipient.collection = collection;
        var rids = this.graphService.generateRids(recipient);
        var dh_public_key = this.graphService.keys[rids.rid].dh_public_keys[0];
        var dh_private_key = this.graphService.keys[rids.rid].dh_private_keys[0];
        var privk = new Uint8Array(dh_private_key.match(/[\da-f]{2}/gi).map(function (h) {
            return parseInt(h, 16);
        }));
        var pubk = new Uint8Array(dh_public_key.match(/[\da-f]{2}/gi).map(function (h) {
            return parseInt(h, 16);
        }));
        var shared_secret = this.toHex(X25519.getSharedKey(privk, pubk));
        var request = __assign({}, rids, { relationship: {}, shared_secret: shared_secret });
        request.relationship[collection] = relationship;
        return this.transactionService.generateTransaction(request)
            .then(function () {
            _this.sendnewtxn();
        });
    };
    WebSocketService.prototype.sendnewtxn = function () {
        return this.websocket.send(JSON.stringify({
            id: '',
            jsonrpc: 2.0,
            method: 'newtxn',
            params: {
                transaction: this.transactionService.transaction
            }
        }));
    };
    WebSocketService.prototype.toHex = function (byteArray) {
        var callback = function (byte) {
            return ('0' + (byte & 0xFF).toString(16)).slice(-2);
        };
        return Array.from(byteArray, callback).join('');
    };
    WebSocketService = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["B" /* Injectable */])(),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_3__angular_http__["b" /* Http */],
            __WEBPACK_IMPORTED_MODULE_1__bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_2__settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_5__graph_service__["a" /* GraphService */],
            __WEBPACK_IMPORTED_MODULE_6__transaction_service__["a" /* TransactionService */],
            __WEBPACK_IMPORTED_MODULE_4_ionic_angular__["b" /* Events */]])
    ], WebSocketService);
    return WebSocketService;
}());

//# sourceMappingURL=websocket.service.js.map

/***/ }),

/***/ 398:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return SignatureRequestPage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(5);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__app_graph_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_bulletinSecret_service__ = __webpack_require__(14);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_settings_service__ = __webpack_require__(10);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};





var SignatureRequestPage = /** @class */ (function () {
    function SignatureRequestPage(navCtrl, navParams, graphService, bulletinSecretService, settingsService) {
        this.navCtrl = navCtrl;
        this.navParams = navParams;
        this.graphService = graphService;
        this.bulletinSecretService = bulletinSecretService;
        this.settingsService = settingsService;
    }
    SignatureRequestPage = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["n" /* Component */])({
            selector: 'page-signaturerequest',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/signaturerequest/signaturerequest.html"*/''/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/signaturerequest/signaturerequest.html"*/
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["i" /* NavController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["j" /* NavParams */],
            __WEBPACK_IMPORTED_MODULE_2__app_graph_service__["a" /* GraphService */],
            __WEBPACK_IMPORTED_MODULE_3__app_bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_4__app_settings_service__["a" /* SettingsService */]])
    ], SignatureRequestPage);
    return SignatureRequestPage;
}());

//# sourceMappingURL=signaturerequest.js.map

/***/ }),

/***/ 399:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return MarketPage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(5);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__app_graph_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_settings_service__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_smartContract_service__ = __webpack_require__(68);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__assets_assets__ = __webpack_require__(230);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__createpromo__ = __webpack_require__(403);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__marketitem__ = __webpack_require__(139);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};








var MarketPage = /** @class */ (function () {
    function MarketPage(navCtrl, navParams, graphService, settingsService, smartContractService) {
        var _this = this;
        this.navCtrl = navCtrl;
        this.navParams = navParams;
        this.graphService = graphService;
        this.settingsService = settingsService;
        this.smartContractService = smartContractService;
        this.item = this.navParams.get('item');
        this.market = this.item.relationship[this.settingsService.collections.MARKET];
        setInterval(function () {
            if (_this.prevHeight < _this.settingsService.latest_block.height)
                _this.refresh();
        }, 1000);
    }
    MarketPage.prototype.ionViewDidEnter = function () {
        this.refresh();
    };
    MarketPage.prototype.refresh = function (e) {
        var _this = this;
        if (e === void 0) { e = null; }
        this.graphService.getBlockHeight()
            .then(function (data) {
            _this.settingsService.latest_block = data;
        })
            .then(function () {
            return _this.graphService.getSmartContracts(_this.market);
        })
            .then(function (smartContracts) {
            _this.smartContracts = smartContracts.filter(function (item) {
                try {
                    var sc = item.relationship[_this.settingsService.collections.SMART_CONTRACT];
                    if ((sc.expiry - _this.settingsService.latest_block.height) < 0) {
                        return false;
                    }
                    if (sc.contract_type === _this.smartContractService.contractTypes.CHANGE_OWNERSHIP) {
                        return sc.asset.data.substr(0, 5) === 'data:';
                    }
                }
                catch (err) {
                    return false;
                }
                return true;
            });
            console.log(_this.smartContracts);
            e && e.complete();
        });
    };
    MarketPage.prototype.sellAsset = function () {
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_5__assets_assets__["a" /* AssetsPage */]);
    };
    MarketPage.prototype.startPromotion = function () {
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_6__createpromo__["a" /* CreatePromoPage */], {
            market: this.item
        });
    };
    MarketPage.prototype.itemTapped = function (e, smartContract) {
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_7__marketitem__["a" /* MarketItemPage */], {
            item: smartContract,
            market: this.item
        });
    };
    MarketPage = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["n" /* Component */])({
            selector: 'market-page',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/markets/market.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n  </ion-navbar>\n</ion-header>\n\n<ion-content padding>\n  <ion-refresher (ionRefresh)="refresh($event)">\n    <ion-refresher-content></ion-refresher-content>\n  </ion-refresher>\n  <h1>{{market.username}}</h1>\n  <ion-row *ngIf="smartContracts">\n    <ion-col col-md-3 *ngIf="market.username === \'Marketplace\'">\n      <button ion-button secondary (click)="sellAsset($event)">My assets</button>\n      <ion-card *ngFor="let smartContract of smartContracts" (click)="itemTapped($event, smartContract)" style="cursor: pointer">\n        <ion-card-content>\n          <ion-card-title style="text-overflow:ellipsis;" text-wrap>\n            <img [src]="smartContract.relationship[settingsService.collections.SMART_CONTRACT].asset.data">\n          </ion-card-title>\n          <ion-card-content>\n            <div class="resource">{{smartContract.relationship[settingsService.collections.SMART_CONTRACT].asset.identity.username}}</div>\n          </ion-card-content>\n          <ion-card-content>\n            {{smartContract.relationship[settingsService.collections.SMART_CONTRACT].price.toFixed(8)}} YDA\n          </ion-card-content>\n        </ion-card-content>\n      </ion-card>\n    </ion-col>\n    <ion-col col-md-3 *ngIf="market.username === \'Promotions\'">\n      <button ion-button secondary (click)="startPromotion($event)">Start promotion</button>\n      <ion-card *ngFor="let smartContract of smartContracts" (click)="itemTapped($event, smartContract)" style="cursor: pointer">\n        <ion-card-content>\n          <ion-card-content>\n            <div class="resource">{{smartContract.relationship[settingsService.collections.SMART_CONTRACT].target.username}}</div>\n          </ion-card-content>\n        </ion-card-content>\n      </ion-card>\n    </ion-col>\n  </ion-row>\n</ion-content>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/markets/market.html"*/
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["i" /* NavController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["j" /* NavParams */],
            __WEBPACK_IMPORTED_MODULE_2__app_graph_service__["a" /* GraphService */],
            __WEBPACK_IMPORTED_MODULE_3__app_settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_4__app_smartContract_service__["a" /* SmartContractService */]])
    ], MarketPage);
    return MarketPage;
}());

//# sourceMappingURL=market.js.map

/***/ }),

/***/ 400:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return CreateAssetPage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(5);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__app_graph_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_bulletinSecret_service__ = __webpack_require__(14);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_settings_service__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_websocket_service__ = __webpack_require__(37);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_transaction_service__ = __webpack_require__(20);
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








var CreateAssetPage = /** @class */ (function () {
    function CreateAssetPage(navCtrl, navParams, graphService, bulletinSecretService, settingsService, websocketService, transactionService, alertCtrl, ahttp) {
        this.navCtrl = navCtrl;
        this.navParams = navParams;
        this.graphService = graphService;
        this.bulletinSecretService = bulletinSecretService;
        this.settingsService = settingsService;
        this.websocketService = websocketService;
        this.transactionService = transactionService;
        this.alertCtrl = alertCtrl;
        this.ahttp = ahttp;
    }
    CreateAssetPage.prototype.changeListener = function ($event) {
        var _this = this;
        this.busy = true;
        if (!$event.target.files[0]) {
            this.filedata = '';
            return;
        }
        this.filepath = $event.target.files[0].name;
        var reader = new FileReader();
        reader.readAsDataURL($event.target.files[0]);
        reader.onload = function () {
            _this.data = reader.result.toString();
            if (_this.data.length > 5000) {
                alert('File too large. Please select a smaller file.');
                return;
            }
            _this.filedata = _this.data;
        };
        reader.onerror = function () { };
    };
    CreateAssetPage.prototype.save = function () {
        var _this = this;
        var alert = this.alertCtrl.create();
        alert.setTitle('Create Asset');
        alert.setSubTitle('Are you sure you want to save this asset?');
        alert.addButton({
            text: 'Continue editing'
        });
        var key = foobar.bitcoin.ECPair.makeRandom();
        var wif = key.toWIF();
        var username_signature = foobar.base64.fromByteArray(key.sign(foobar.bitcoin.crypto.sha256(this.username)).toDER());
        var public_key = key.getPublicKeyBuffer().toString('hex');
        var identity = {
            username: this.username,
            username_signature: username_signature,
            public_key: public_key,
            wif: wif,
            collection: this.settingsService.collections.ASSET
        };
        try {
            this.data = JSON.parse(this.data);
        }
        catch (err) {
        }
        alert.addButton({
            text: 'Save',
            handler: function (data) {
                var rids = _this.graphService.generateRids(identity, null, _this.settingsService.collections.ASSET);
                _this.websocketService.newtxn({
                    identity: identity,
                    data: _this.data,
                    checksum: forge.sha256.create().update(_this.data + identity.username_signature).digest().toHex()
                }, rids, _this.settingsService.collections.ASSET)
                    .then(function () {
                    _this.navCtrl.pop();
                });
            }
        });
        alert.present();
    };
    CreateAssetPage = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["n" /* Component */])({
            selector: 'create-asset',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/assets/createasset.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n  </ion-navbar>\n</ion-header>\n\n<ion-content padding>\n  <ion-refresher (ionRefresh)="refresh($event)">\n    <ion-refresher-content></ion-refresher-content>\n  </ion-refresher>\n  <h1>Asset name</h1>\n  <ion-item>\n    <ion-input type="text" [(ngModel)]="username" placeholder="Enter the name of your asset"></ion-input>\n  </ion-item>\n  <h1>Asset data</h1>\n  <ion-item>\n    <ion-input type="file" (change)="changeListener($event)"></ion-input> (20KB maximum file size)\n  </ion-item>\n  <ion-item *ngIf="filedata">\n    <img [src]="filedata">\n  </ion-item>\n  <ion-item>\n    <button ion-button secondary (click)="save()" [disabled]="!username || !data">Save</button>\n  </ion-item>\n</ion-content>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/assets/createasset.html"*/
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["i" /* NavController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["j" /* NavParams */],
            __WEBPACK_IMPORTED_MODULE_2__app_graph_service__["a" /* GraphService */],
            __WEBPACK_IMPORTED_MODULE_3__app_bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_4__app_settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_5__app_websocket_service__["a" /* WebSocketService */],
            __WEBPACK_IMPORTED_MODULE_6__app_transaction_service__["a" /* TransactionService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["a" /* AlertController */],
            __WEBPACK_IMPORTED_MODULE_7__angular_http__["b" /* Http */]])
    ], CreateAssetPage);
    return CreateAssetPage;
}());

//# sourceMappingURL=createasset.js.map

/***/ }),

/***/ 401:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return AssetItemPage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(5);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__app_bulletinSecret_service__ = __webpack_require__(14);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_graph_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_transaction_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_settings_service__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__app_smartContract_service__ = __webpack_require__(68);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__app_websocket_service__ = __webpack_require__(37);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__markets_createsale__ = __webpack_require__(402);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};










var AssetItemPage = /** @class */ (function () {
    function AssetItemPage(navCtrl, navParams, walletService, graphService, bulletinSecretService, alertCtrl, transactionService, settingsService, smartContractService, websocketService) {
        this.navCtrl = navCtrl;
        this.navParams = navParams;
        this.walletService = walletService;
        this.graphService = graphService;
        this.bulletinSecretService = bulletinSecretService;
        this.alertCtrl = alertCtrl;
        this.transactionService = transactionService;
        this.settingsService = settingsService;
        this.smartContractService = smartContractService;
        this.websocketService = websocketService;
        this.item = navParams.data.item;
        this.asset = this.item.relationship[this.settingsService.collections.ASSET];
        this.market = graphService.graph.markets.filter(function (market) { return market.relationship[settingsService.collections.MARKET].username === 'Marketplace'; })[0];
    }
    AssetItemPage.prototype.sell = function (e, market) {
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_9__markets_createsale__["a" /* CreateSalePage */], {
            item: this.item,
            market: this.market
        });
    };
    AssetItemPage.prototype.toHex = function (byteArray) {
        var callback = function (byte) {
            return ('0' + (byte & 0xFF).toString(16)).slice(-2);
        };
        return Array.from(byteArray, callback).join('');
    };
    AssetItemPage = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["n" /* Component */])({
            selector: 'asset-item',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/assets/assetitem.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n  </ion-navbar>\n</ion-header>\n\n<ion-content padding>\n  <ion-refresher (ionRefresh)="refresh($event)">\n    <ion-refresher-content></ion-refresher-content>\n  </ion-refresher>\n  <h1>Asset</h1>\n  <ion-item>\n    {{asset.identity.username}}\n  </ion-item>\n  <ion-item>\n    <img [src]="asset.data">\n  </ion-item>\n  <ion-item>\n    {{market.relationship[settingsService.collections.MARKET].username}} <button ion-button secondary (click)="sell($event, market)">Sell asset in this market</button>\n  </ion-item>\n</ion-content>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/assets/assetitem.html"*/
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["i" /* NavController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["j" /* NavParams */],
            __WEBPACK_IMPORTED_MODULE_5__app_wallet_service__["a" /* WalletService */],
            __WEBPACK_IMPORTED_MODULE_3__app_graph_service__["a" /* GraphService */],
            __WEBPACK_IMPORTED_MODULE_2__app_bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["a" /* AlertController */],
            __WEBPACK_IMPORTED_MODULE_4__app_transaction_service__["a" /* TransactionService */],
            __WEBPACK_IMPORTED_MODULE_6__app_settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_7__app_smartContract_service__["a" /* SmartContractService */],
            __WEBPACK_IMPORTED_MODULE_8__app_websocket_service__["a" /* WebSocketService */]])
    ], AssetItemPage);
    return AssetItemPage;
}());

//# sourceMappingURL=assetitem.js.map

/***/ }),

/***/ 402:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return CreateSalePage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(5);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__app_graph_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_bulletinSecret_service__ = __webpack_require__(14);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_settings_service__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_websocket_service__ = __webpack_require__(37);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_transaction_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__angular_http__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__app_smartContract_service__ = __webpack_require__(68);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__marketitem__ = __webpack_require__(139);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};










var CreateSalePage = /** @class */ (function () {
    function CreateSalePage(navCtrl, navParams, graphService, bulletinSecretService, settingsService, websocketService, transactionService, alertCtrl, ahttp, smartContractService) {
        var _this = this;
        this.navCtrl = navCtrl;
        this.navParams = navParams;
        this.graphService = graphService;
        this.bulletinSecretService = bulletinSecretService;
        this.settingsService = settingsService;
        this.websocketService = websocketService;
        this.transactionService = transactionService;
        this.alertCtrl = alertCtrl;
        this.ahttp = ahttp;
        this.smartContractService = smartContractService;
        this.marketTxn = this.navParams.get('market');
        this.market = this.marketTxn.relationship[this.settingsService.collections.MARKET];
        this.item = this.navParams.get('item');
        this.asset = this.item.relationship[this.settingsService.collections.ASSET];
        this.proof_type = this.smartContractService.assetProofTypes.FIRST_COME;
        this.graphService.getBlockHeight()
            .then(function (data) {
            _this.settingsService.latest_block = data;
        });
    }
    CreateSalePage.prototype.presentError = function (field) {
        var alert = this.alertCtrl.create();
        alert.setTitle('Missing field');
        alert.setSubTitle('Please enter information for ' + field + '.');
        alert.addButton({
            text: 'Ok'
        });
        alert.present();
    };
    CreateSalePage.prototype.save = function () {
        var _this = this;
        if (!this.price) {
            this.presentError('price');
            return;
        }
        if (!this.proof_type) {
            this.presentError('proof_type');
            return;
        }
        var alert = this.alertCtrl.create();
        alert.setTitle('Sell Asset');
        alert.setSubTitle('Are you sure you want to sell this asset?');
        alert.addButton({
            text: 'Continue editing'
        });
        alert.addButton({
            text: 'Confirm',
            handler: function (data) {
                var contract = _this.smartContractService.generateChangeOfOwnership(_this.asset, _this.graphService.toIdentity(_this.bulletinSecretService.cloneIdentity()), parseFloat(_this.price), _this.proof_type, _this.market, _this.expiry);
                var rids = _this.graphService.generateRids(contract.identity, _this.market, _this.settingsService.collections.SMART_CONTRACT);
                _this.websocketService.newtxn(contract, rids, _this.settingsService.collections.SMART_CONTRACT, _this.market.username_signature)
                    .then(function (smartContract) {
                    smartContract.relationship[_this.settingsService.collections.SMART_CONTRACT][_this.settingsService.collections.ASSET] = _this.asset;
                    smartContract.relationship[_this.settingsService.collections.SMART_CONTRACT].creator = _this.graphService.toIdentity(_this.bulletinSecretService.cloneIdentity());
                    smartContract.pending = true;
                    _this.navCtrl.setRoot(__WEBPACK_IMPORTED_MODULE_9__marketitem__["a" /* MarketItemPage */], {
                        item: smartContract,
                        market: _this.marketTxn
                    });
                });
            }
        });
        alert.present();
    };
    CreateSalePage = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["n" /* Component */])({
            selector: 'create-sale',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/markets/createsale.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n  </ion-navbar>\n</ion-header>\n\n<ion-content padding>\n  <ion-refresher (ionRefresh)="refresh($event)">\n    <ion-refresher-content></ion-refresher-content>\n  </ion-refresher>\n  <h1>Create new sale</h1>\n  <ion-row>\n    <ion-col col-md-4>\n      <h3>Asset info</h3>\n      <ion-card ion-item style="">\n        <ion-card-title style="text-overflow:ellipsis;" text-wrap>\n          <img [src]="asset.data">\n        </ion-card-title>\n        <ion-card-content>\n          {{asset.identity.username}}\n        </ion-card-content>\n      </ion-card>\n    </ion-col>\n    <ion-col col-md-4>\n      <h3>Sale info</h3>\n      <ion-item>\n        <ion-label color="primary">Price</ion-label>\n        <ion-input type="number" [(ngModel)]="price" placeholder="What\'s the price of this asset?"></ion-input>\n      </ion-item>\n      <ion-item>\n        <ion-label color="primary">Expires</ion-label>\n        <ion-input type="number" [(ngModel)]="expiry" placeholder="How many blocks until this sale ends?"></ion-input>\n      </ion-item>\n      <h3>Sale type</h3>\n      <ion-list radio-group [(ngModel)]="proof_type">\n        <ion-item>\n          <ion-label>Buy now</ion-label>\n          <ion-radio value="first_come" checked></ion-radio>\n        </ion-item>\n        <ion-item>\n          <ion-label>Auction</ion-label>\n          <ion-radio value="auction"></ion-radio>\n        </ion-item>\n      </ion-list>\n      <ion-item>\n        <button ion-button secondary (click)="save()" [disabled]="!price">Confirm</button>\n      </ion-item>\n    </ion-col>\n  </ion-row>\n</ion-content>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/markets/createsale.html"*/
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["i" /* NavController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["j" /* NavParams */],
            __WEBPACK_IMPORTED_MODULE_2__app_graph_service__["a" /* GraphService */],
            __WEBPACK_IMPORTED_MODULE_3__app_bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_4__app_settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_5__app_websocket_service__["a" /* WebSocketService */],
            __WEBPACK_IMPORTED_MODULE_6__app_transaction_service__["a" /* TransactionService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["a" /* AlertController */],
            __WEBPACK_IMPORTED_MODULE_7__angular_http__["b" /* Http */],
            __WEBPACK_IMPORTED_MODULE_8__app_smartContract_service__["a" /* SmartContractService */]])
    ], CreateSalePage);
    return CreateSalePage;
}());

//# sourceMappingURL=createsale.js.map

/***/ }),

/***/ 403:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return CreatePromoPage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(5);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__app_graph_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_bulletinSecret_service__ = __webpack_require__(14);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_settings_service__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_websocket_service__ = __webpack_require__(37);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_transaction_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__angular_forms__ = __webpack_require__(30);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__angular_http__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__app_smartContract_service__ = __webpack_require__(68);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_10__app_autocomplete_provider__ = __webpack_require__(110);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_11__app_wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_12__marketitem__ = __webpack_require__(139);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};













var CreatePromoPage = /** @class */ (function () {
    function CreatePromoPage(navCtrl, navParams, graphService, bulletinSecretService, settingsService, websocketService, transactionService, alertCtrl, ahttp, smartContractService, completeTestService, walletService) {
        var _this = this;
        this.navCtrl = navCtrl;
        this.navParams = navParams;
        this.graphService = graphService;
        this.bulletinSecretService = bulletinSecretService;
        this.settingsService = settingsService;
        this.websocketService = websocketService;
        this.transactionService = transactionService;
        this.alertCtrl = alertCtrl;
        this.ahttp = ahttp;
        this.smartContractService = smartContractService;
        this.completeTestService = completeTestService;
        this.walletService = walletService;
        this.myForm = new __WEBPACK_IMPORTED_MODULE_7__angular_forms__["b" /* FormGroup */]({
            searchTerm: new __WEBPACK_IMPORTED_MODULE_7__angular_forms__["a" /* FormControl */]('', [__WEBPACK_IMPORTED_MODULE_7__angular_forms__["g" /* Validators */].required])
        });
        this.marketTxn = this.navParams.get('market');
        this.market = this.marketTxn.relationship[this.settingsService.collections.MARKET];
        this.proof_type = this.smartContractService.promoProofTypes.HONOR;
        this.pay_referrer = true;
        this.pay_referrer_operator = this.smartContractService.payoutOperators.FIXED;
        this.pay_referrer_payout_type = this.smartContractService.payoutType.ONE_TIME;
        this.pay_referrer_amount = 1;
        this.pay_referee = true;
        this.pay_referee_operator = this.smartContractService.payoutOperators.FIXED;
        this.pay_referee_payout_type = this.smartContractService.payoutType.ONE_TIME;
        this.pay_referee_amount = 1;
        this.promotedIdentity = 'me';
        this.fund_amount = 1;
        this.expiry = 1000;
        this.graphService.getBlockHeight()
            .then(function (data) {
            _this.settingsService.latest_block = data;
        });
    }
    CreatePromoPage.prototype.promotedIdentityChanged = function () {
        if (this.promotedIdentity === 'me') {
            this.selectedIdentity = this.graphService.toIdentity(this.bulletinSecretService.identity);
        }
        else {
            this.selectedIdentity = '';
        }
    };
    CreatePromoPage.prototype.contactSearchChanged = function () {
        this.promotedIdentity = 'contact';
    };
    CreatePromoPage.prototype.presentError = function (field) {
        var alert = this.alertCtrl.create();
        alert.setTitle('Missing field');
        alert.setSubTitle('Please enter information for ' + field + '.');
        alert.addButton({
            text: 'Ok'
        });
        alert.present();
    };
    CreatePromoPage.prototype.save = function () {
        var _this = this;
        if (this.pay_referrer === true) {
            if (!this.pay_referrer_operator) {
                this.presentError('pay_referrer_operator');
                return;
            }
            if (!this.pay_referrer_payout_type) {
                this.presentError('pay_referrer_payout_type');
                return;
            }
            if (this.pay_referrer_payout_type === this.smartContractService.payoutType.RECURRING &&
                !this.pay_referrer_payout_interval) {
                this.presentError('pay_referrer_payout_interval');
                return;
            }
            if (!this.pay_referrer_amount) {
                this.presentError('pay_referrer_amount');
                return;
            }
        }
        if (this.pay_referee === true) {
            if (!this.pay_referee_operator) {
                this.presentError('pay_referee_operator');
                return;
            }
            if (!this.pay_referee_payout_type) {
                this.presentError('pay_referee_payout_type');
                return;
            }
            if (this.pay_referee_payout_type === this.smartContractService.payoutType.RECURRING &&
                !this.pay_referee_payout_interval) {
                this.presentError('pay_referee_payout_interval');
                return;
            }
            if (!this.pay_referee_amount) {
                this.presentError('pay_referee_amount');
                return;
            }
        }
        if (!this.pay_referrer === true && !this.pay_referee === true) {
            this.presentError('pay_referrer and pay_referee');
            return;
        }
        if (!this.fund_amount) {
            this.presentError('fund_amount');
            return;
        }
        if (!this.expiry) {
            this.presentError('expiry');
            return;
        }
        var alert = this.alertCtrl.create();
        alert.setTitle('Start promotion');
        alert.setSubTitle('Are you sure you want to start this promotion?');
        alert.addButton({
            text: 'Continue editing'
        });
        alert.addButton({
            text: 'Confirm',
            handler: function (data) {
                var selectedIdentity;
                if (_this.promotedIdentity === 'me') {
                    selectedIdentity = _this.graphService.toIdentity(_this.bulletinSecretService.cloneIdentity());
                }
                else {
                    selectedIdentity = _this.selectedIdentityForm;
                }
                _this.walletService.get(_this.fund_amount)
                    .then(function () {
                    var contract = _this.smartContractService.generateNewRelationshipPromo(_this.graphService.toIdentity(_this.bulletinSecretService.cloneIdentity()), _this.proof_type, selectedIdentity, _this.market, _this.pay_referrer, _this.pay_referrer_operator, _this.pay_referrer_payout_type, parseInt(_this.pay_referrer_payout_interval), parseFloat(_this.pay_referrer_amount), _this.pay_referee, _this.pay_referee_operator, _this.pay_referee_payout_type, parseInt(_this.pay_referee_payout_interval), parseFloat(_this.pay_referee_amount), parseInt(_this.expiry));
                    var rids = _this.graphService.generateRids(contract.identity, _this.market, _this.settingsService.collections.SMART_CONTRACT);
                    var contractAddress = foobar.bitcoin.ECPair.fromPublicKeyBuffer(foobar.Buffer.Buffer.from(contract.identity.public_key, 'hex')).getAddress();
                    var outputs = [];
                    if ((contract.referee.active && contract.referee.operator === _this.smartContractService.payoutOperators.FIXED) ||
                        (contract.referrer.active && contract.referrer.operator === _this.smartContractService.payoutOperators.FIXED)) {
                        outputs.push({
                            to: contractAddress,
                            value: parseFloat(_this.fund_amount)
                        });
                    }
                    return _this.websocketService.newtxn(contract, rids, _this.settingsService.collections.SMART_CONTRACT, _this.market.username_signature, { outputs: outputs });
                }).then(function (smartContract) {
                    smartContract.relationship[_this.settingsService.collections.SMART_CONTRACT][_this.settingsService.collections.ASSET] = _this.asset;
                    smartContract.relationship[_this.settingsService.collections.SMART_CONTRACT].creator = _this.graphService.toIdentity(_this.bulletinSecretService.cloneIdentity());
                    smartContract.pending = true;
                    _this.navCtrl.setRoot(__WEBPACK_IMPORTED_MODULE_12__marketitem__["a" /* MarketItemPage */], {
                        item: smartContract,
                        market: _this.marketTxn
                    });
                });
            }
        });
        alert.present();
    };
    CreatePromoPage = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["n" /* Component */])({
            selector: 'create-promo',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/markets/createpromo.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n  </ion-navbar>\n</ion-header>\n\n<ion-content padding>\n  <ion-refresher (ionRefresh)="refresh($event)">\n    <ion-refresher-content></ion-refresher-content>\n  </ion-refresher>\n  <h1>Start new promotion</h1>\n  <ion-row>\n    <ion-col col-md-4>\n      <h3>Promotion info</h3>\n      <h3>Proof type</h3>\n      <ion-list radio-group [(ngModel)]="proof_type">\n        <ion-item>\n          <ion-label>{{smartContractService.promoProofTypes.HONOR}}</ion-label>\n          <ion-radio [value]="smartContractService.promoProofTypes.HONOR" checked></ion-radio>\n        </ion-item>\n        <ion-item>\n          <ion-label>{{smartContractService.promoProofTypes.CONFIRMATION}}</ion-label>\n          <ion-radio [value]="smartContractService.promoProofTypes.CONFIRMATION"></ion-radio>\n        </ion-item>\n      </ion-list>\n      <h3>Identity to promote</h3>\n      <ion-list radio-group [(ngModel)]="promotedIdentity" (change)="promotedIdentityChanged()">\n        <ion-item>\n          <ion-label>Promote myself</ion-label>\n          <ion-radio value="me" checked></ion-radio>\n        </ion-item>\n        <ion-item>\n          <ion-label>Promote a contact</ion-label>\n          <ion-radio value="contact"></ion-radio>\n        </ion-item>\n        <form [formGroup]="myForm" (change)="contactSearchChanged()">\n          <ion-auto-complete #searchbar [(ngModel)]="selectedIdentityForm" [options]="{ placeholder : \'Recipient\' }" [dataProvider]="completeTestService" formControlName="searchTerm" required></ion-auto-complete>\n        </form>\n      </ion-list>\n      <h3>Referrer payout</h3>\n      <ion-list radio-group [(ngModel)]="pay_referrer">\n        <ion-item>\n          <ion-label>Yes</ion-label>\n          <ion-radio [value]="true"></ion-radio>\n        </ion-item>\n        <ion-item>\n          <ion-label>No</ion-label>\n          <ion-radio [value]="false" checked></ion-radio>\n        </ion-item>\n      </ion-list>\n      <ng-container *ngIf="pay_referrer">\n        <h3>Type</h3>\n        <ion-list radio-group [(ngModel)]="pay_referrer_operator">\n          <ion-item>\n            <ion-label>{{smartContractService.payoutOperators.FIXED}}</ion-label>\n            <ion-radio [value]="smartContractService.payoutOperators.FIXED" checked></ion-radio>\n          </ion-item>\n          <ion-item>\n            <ion-label>{{smartContractService.payoutOperators.PERCENT}}</ion-label>\n            <ion-radio [value]="smartContractService.payoutOperators.PERCENT"></ion-radio>\n          </ion-item>\n        </ion-list>\n        <h3>Term</h3>\n        <ion-list radio-group [(ngModel)]="pay_referrer_payout_type">\n          <ion-item>\n            <ion-label>{{smartContractService.payoutType.ONE_TIME}}</ion-label>\n            <ion-radio [value]="smartContractService.payoutType.ONE_TIME" checked></ion-radio>\n          </ion-item>\n          <ion-item>\n            <ion-label>{{smartContractService.payoutType.RECURRING}}</ion-label>\n            <ion-radio [value]="smartContractService.payoutType.RECURRING"></ion-radio>\n          </ion-item>\n        </ion-list>\n        <ion-item *ngIf="pay_referrer_payout_type === smartContractService.payoutType.RECURRING">\n          <ion-label color="primary">Payment interval</ion-label>\n          <ion-input type="number" [(ngModel)]="pay_referrer_payout_interval" placeholder="How many blocks between payouts?"></ion-input>\n        </ion-item>\n        <h3>Amount</h3>\n        <ion-item *ngIf="pay_referrer_operator === smartContractService.payoutOperators.FIXED">\n          <ion-label>{{smartContractService.payoutOperators.FIXED}}</ion-label>\n          <ion-input type="number" [(ngModel)]="pay_referrer_amount" placeholder="How much to pay the referrer?"></ion-input>\n        </ion-item>\n        <ion-item *ngIf="pay_referrer_operator === smartContractService.payoutOperators.PERCENT">\n          <ion-label>{{smartContractService.payoutOperators.PERCENT}}</ion-label>\n          <ion-input type="number" min="0.0" max="1.0" step="0.1" [(ngModel)]="pay_referrer_amount" placeholder="What percentage does the referrer get?"></ion-input>\n        </ion-item>\n      </ng-container>\n      <h3>Referree payout</h3>\n      <ion-list radio-group [(ngModel)]="pay_referee">\n        <ion-item>\n          <ion-label>Yes</ion-label>\n          <ion-radio [value]="true"></ion-radio>\n        </ion-item>\n        <ion-item>\n          <ion-label>No</ion-label>\n          <ion-radio [value]="false" checked></ion-radio>\n        </ion-item>\n      </ion-list>\n      <ng-container *ngIf="pay_referee">\n        <h3>Type</h3>\n        <ion-list radio-group [(ngModel)]="pay_referee_operator">\n          <ion-item>\n            <ion-label>{{smartContractService.payoutOperators.FIXED}}</ion-label>\n            <ion-radio [value]="smartContractService.payoutOperators.FIXED" checked></ion-radio>\n          </ion-item>\n          <ion-item>\n            <ion-label>{{smartContractService.payoutOperators.PERCENT}}</ion-label>\n            <ion-radio [value]="smartContractService.payoutOperators.PERCENT"></ion-radio>\n          </ion-item>\n        </ion-list>\n        <h3>Term</h3>\n        <ion-list radio-group [(ngModel)]="pay_referee_payout_type">\n          <ion-item>\n            <ion-label>{{smartContractService.payoutType.ONE_TIME}}</ion-label>\n            <ion-radio [value]="smartContractService.payoutType.ONE_TIME" checked></ion-radio>\n          </ion-item>\n          <ion-item>\n            <ion-label>{{smartContractService.payoutType.RECURRING}}</ion-label>\n            <ion-radio [value]="smartContractService.payoutType.RECURRING"></ion-radio>\n          </ion-item>\n        </ion-list>\n        <ion-item *ngIf="pay_referee_payout_type === smartContractService.payoutType.RECURRING">\n          <ion-label color="primary">Payment interval</ion-label>\n          <ion-input type="number" [(ngModel)]="pay_referee_payout_interval" placeholder="How many blocks between payouts?"></ion-input>\n        </ion-item>\n        <h3>Amount</h3>\n        <ion-item *ngIf="pay_referee_operator === smartContractService.payoutOperators.FIXED">\n          <ion-label>{{smartContractService.payoutOperators.FIXED}}</ion-label>\n          <ion-input type="number" [(ngModel)]="pay_referee_amount" placeholder="How much to pay the referee?"></ion-input>\n        </ion-item>\n        <ion-item *ngIf="pay_referee_operator === smartContractService.payoutOperators.PERCENT">\n          <ion-label>{{smartContractService.payoutOperators.PERCENT}}</ion-label>\n          <ion-input type="number" min="0.0" max="1.0" step="0.1" [(ngModel)]="pay_referee_amount" placeholder="What percentage does the referee?"></ion-input>\n        </ion-item>\n      </ng-container>\n      <ng-container *ngIf="pay_referee_operator === smartContractService.payoutOperators.FIXED || pay_referrer_operator === smartContractService.payoutOperators.FIXED">\n        <h3>Contract fund</h3>\n        <ion-item>\n          <ion-label color="primary">Fund amount</ion-label>\n          <ion-input type="number" [(ngModel)]="fund_amount" placeholder="How much YDA to fund this promotion?"></ion-input>\n        </ion-item>\n        <ion-item>\n          <ion-label color="primary">Expiry</ion-label>\n          <ion-input type="number" [(ngModel)]="expiry" placeholder="Expires in how many blocks?"></ion-input>\n        </ion-item>\n      </ng-container>\n      <h3>&nbsp;</h3>\n      <ion-item>\n        <button ion-button secondary (click)="save()">Confirm</button>\n      </ion-item>\n    </ion-col>\n  </ion-row>\n</ion-content>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/markets/createpromo.html"*/
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["i" /* NavController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["j" /* NavParams */],
            __WEBPACK_IMPORTED_MODULE_2__app_graph_service__["a" /* GraphService */],
            __WEBPACK_IMPORTED_MODULE_3__app_bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_4__app_settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_5__app_websocket_service__["a" /* WebSocketService */],
            __WEBPACK_IMPORTED_MODULE_6__app_transaction_service__["a" /* TransactionService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["a" /* AlertController */],
            __WEBPACK_IMPORTED_MODULE_8__angular_http__["b" /* Http */],
            __WEBPACK_IMPORTED_MODULE_9__app_smartContract_service__["a" /* SmartContractService */],
            __WEBPACK_IMPORTED_MODULE_10__app_autocomplete_provider__["a" /* CompleteTestService */],
            __WEBPACK_IMPORTED_MODULE_11__app_wallet_service__["a" /* WalletService */]])
    ], CreatePromoPage);
    return CreatePromoPage;
}());

//# sourceMappingURL=createpromo.js.map

/***/ }),

/***/ 405:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return Settings; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(5);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__ionic_storage__ = __webpack_require__(48);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_settings_service__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_peer_service__ = __webpack_require__(226);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_bulletinSecret_service__ = __webpack_require__(14);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_firebase_service__ = __webpack_require__(231);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__list_list__ = __webpack_require__(69);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__app_graph_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__app_wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_10__app_transaction_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_11__ionic_native_social_sharing__ = __webpack_require__(108);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_12__home_home__ = __webpack_require__(225);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_13__angular_http__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_14__ionic_native_geolocation__ = __webpack_require__(224);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_15__ionic_native_google_maps__ = __webpack_require__(406);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_16__app_websocket_service__ = __webpack_require__(37);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_17__app_groups__ = __webpack_require__(683);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_18__mail_mail__ = __webpack_require__(232);
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
    function Settings(navCtrl, navParams, settingsService, bulletinSecretService, firebaseService, loadingCtrl, alertCtrl, storage, graphService, socialSharing, walletService, websocketService, transactionService, events, toastCtrl, peerService, ahttp, geolocation, platform) {
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
        this.websocketService = websocketService;
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
    Settings.prototype.importKey = function (wif) {
        var _this = this;
        if (wif === void 0) { wif = null; }
        return new Promise(function (resolve, reject) {
            if (wif)
                return resolve(wif);
            var alert = _this.alertCtrl.create({
                title: 'Set WIF',
                inputs: [
                    {
                        name: 'wif',
                        placeholder: 'WIF'
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
                        text: 'Continue',
                        handler: function (data) {
                            resolve(data.wif);
                        }
                    }
                ]
            });
            alert.present();
        })
            .then(function (wifkey) {
            return new Promise(function (resolve, reject) {
                wif = wifkey;
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
        })
            .then(function (username) {
            return _this.bulletinSecretService.import(wif, username);
        })
            .then(function (wif) {
            var toast = _this.toastCtrl.create({
                message: 'Identity created',
                duration: 2000
            });
            toast.present();
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
    Settings.prototype.getPromo = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            var alert = _this.alertCtrl.create({
                title: 'Set promo code',
                inputs: [
                    {
                        name: 'promo',
                        placeholder: 'Promo code'
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
                        text: 'confirm',
                        handler: function (data) {
                            resolve(data.promo);
                        }
                    }
                ]
            });
            alert.present();
        });
    };
    Settings.prototype.createWalletFromInvite = function () {
        var _this = this;
        var promise;
        var username;
        var userType;
        var userParent;
        var invite;
        var promo;
        this.loadingModal = this.loadingCtrl.create({
            content: 'initializing...'
        });
        this.loadingModal.present();
        promise = this.getInvite()
            .then(function () {
            return _this.getPromo();
        })
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
        return this.getUsername()
            .then(function (uname) {
            username = uname;
            return _this.createKey(username);
        })
            .then(function () {
            return _this.refresh(null);
        })
            .then(function () {
            return _this.selectIdentity(username, false);
        })
            .then(function () {
            return _this.graphService.refreshFriendsAndGroups();
        })
            .then(function () {
            _this.loadingModal.dismiss();
        })
            .catch(function () {
            _this.loadingModal.dismiss();
        })
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
                return _this.websocketService.init();
            })
                .then(function () {
                if (showModal) {
                    _this.loadingModal.dismiss();
                }
                _this.settingsService.menu = 'mail';
                _this.events.publish('menu', [
                    { title: 'Inbox', label: 'Inbox', component: __WEBPACK_IMPORTED_MODULE_18__mail_mail__["a" /* MailPage */], count: false, color: '', root: true },
                    { title: 'Sent', label: 'Sent', component: __WEBPACK_IMPORTED_MODULE_18__mail_mail__["a" /* MailPage */], count: false, color: '', root: true }
                ]);
            })
                .catch(function (err) {
                console.log(err);
                if (showModal) {
                    _this.loadingModal.dismiss();
                }
            });
        }
        else {
            var addedDefaults_1 = false;
            return this.set(key)
                .then(function () {
                return _this.graphService.refreshFriendsAndGroups();
            })
                .then(function () {
                var promises = [];
                for (var i = 0; i < __WEBPACK_IMPORTED_MODULE_17__app_groups__["a" /* default */].default_groups.length; i++) {
                    if (!_this.graphService.isAdded(__WEBPACK_IMPORTED_MODULE_17__app_groups__["a" /* default */].default_groups[i])) {
                        promises.push(_this.graphService.addGroup(__WEBPACK_IMPORTED_MODULE_17__app_groups__["a" /* default */].default_groups[i], undefined, undefined, undefined, false));
                        addedDefaults_1 = true;
                    }
                }
                for (var i = 0; i < __WEBPACK_IMPORTED_MODULE_17__app_groups__["a" /* default */].default_markets.length; i++) {
                    if (!_this.graphService.isAdded(__WEBPACK_IMPORTED_MODULE_17__app_groups__["a" /* default */].default_markets[i])) {
                        promises.push(_this.graphService.addGroup(__WEBPACK_IMPORTED_MODULE_17__app_groups__["a" /* default */].default_markets[i], undefined, undefined, undefined, false));
                        addedDefaults_1 = true;
                    }
                }
                return Promise.all(promises);
            })
                .then(function () {
                return addedDefaults_1 ? _this.graphService.refreshFriendsAndGroups() : null;
            })
                .then(function () {
                if (showModal) {
                    _this.loadingModal.dismiss();
                }
                _this.settingsService.menu = 'home';
                _this.events.publish('menu', [{ title: 'Home', label: 'Home', component: __WEBPACK_IMPORTED_MODULE_12__home_home__["a" /* HomePage */], count: false, color: '', root: true }]);
            })
                .then(function () {
                return _this.websocketService.init();
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
            return _this.importKey(identity.wif);
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
            selector: 'page-settings',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/settings/settings.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n  </ion-navbar>\n</ion-header>\n\n<ion-content padding>\n  <ion-refresher (ionRefresh)="refresh($event)">\n    <ion-refresher-content></ion-refresher-content>\n  </ion-refresher>\n  <h1>Sign-in</h1>\n  <h3>Create an identity</h3>\n  <button ion-button secondary (click)="createWallet()" *ngIf="!settingsService.remoteSettings.restricted">Create identity</button>\n  <button ion-button secondary (click)="createWalletFromInvite()" *ngIf="settingsService.remoteSettings.restricted">Create identity from Code</button>\n  <h3 *ngIf="keys && keys.length > 0">Select an identity</h3>\n  <ion-list>\n    <button *ngFor="let key of keys" ion-item (click)="selectIdentity(key.username)" [color]="key.active ? \'primary\' : settingsService.remoteSettings.restricted ? \'light\' : \'dark\'">\n      <ion-icon name="person" item-start [color]="\'dark\'"></ion-icon>\n      {{key.username}}\n    </button>\n  </ion-list>\n  <ion-list *ngIf="bulletinSecretService.keyname && !centerIdentityExportEnabled">\n    <ion-item>\n      Make the active identity available anywhere using the YadaCoin blockchain and maps provided by Center Identity\n      <button ion-button secondary (click)="enableCenterIdentityExport()">Enable</button>\n    </ion-item>\n  </ion-list>\n  <ion-list *ngIf="bulletinSecretService.keyname && centerIdentityExportEnabled">\n    <ion-item style="background: linear-gradient(90deg, rgba(255,255,255,1) 0%, #191919 75%); color: black;"><img src="assets/center-identity-logo1024x500.png" height="65" style="vertical-align:middle"></ion-item>\n    <ion-item>\n      <ion-input type="text" placeholder="Public username" [(ngModel)]="bulletinSecretService.identity.username" disabled></ion-input>\n    </ion-item>\n    <ion-item>\n      Pick a private username that nobody knows except for you (must be very memorable)\n    </ion-item>\n    <ion-item>\n      Pick a private username that nobody knows except for you (must be very memorable)\n      <ion-input type="text" placeholder="Private username" [(ngModel)]="centerIdentityPrivateUsername"></ion-input>\n    </ion-item>\n    <ion-item>\n      Pick a private location that nobody knows except for you (must be very memorable)\n      <div id="map-export" style="width:500px;height:500px;"></div>\n    </ion-item>\n    <ion-item *ngIf="!centerIdentitySaveSuccess">\n      <button ion-button secondary (click)="saveKeyUsingCenterIdentity()">Save to blockchain</button>\n    </ion-item>\n    <ion-item *ngIf="centerIdentitySaveSuccess">\n      <button ion-button primary (click)="saveKeyUsingCenterIdentity()" disabled>Success!</button>\n    </ion-item>\n  </ion-list>\n  <ion-list *ngIf="bulletinSecretService.keyname">\n    <hr/>\n    <h4>Export wif (private, do not share)</h4>\n    <ion-item *ngIf="!exportKeyEnabled">\n      <button ion-button secondary (click)="exportKey()">Export active identity</button>\n    </ion-item>\n    <ion-item *ngIf="exportKeyEnabled">\n      <ion-input type="text" [(ngModel)]="activeKey"></ion-input>\n    </ion-item>\n    <h4>Public identity (share this with your friends) <ion-spinner *ngIf="busy"></ion-spinner></h4>\n    <ion-item *ngIf="settingsService.remoteSettings.restricted">\n      <ion-textarea type="text" [(ngModel)]="identitySkylink" autoGrow="true" rows=1></ion-textarea>\n    </ion-item>\n    <ion-item *ngIf="!settingsService.remoteSettings.restricted">\n      <ion-textarea type="text" [value]="bulletinSecretService.identityJson()" autoGrow="true" rows="5"></ion-textarea>\n    </ion-item>\n  </ion-list>\n  <h4>Import using location</h4>\n  <ion-item *ngIf="!centerIdentityImportEnabled">\n    <button ion-button secondary (click)="enableCenterIdentityImport()">Choose location</button>\n  </ion-item>\n  <ion-list *ngIf="centerIdentityImportEnabled">\n    <ion-item>\n      Enter your private username\n      <ion-input type="text" placeholder="Private username" [(ngModel)]="centerIdentityPrivateUsername"></ion-input>\n    </ion-item>\n    <ion-item>\n      Select your private location\n      <div id="map-import" style="width:500px;height:500px;"></div>\n    </ion-item>\n    <ion-item *ngIf="!centerIdentityImportSuccess">\n      <button ion-button secondary (click)="getKeyUsingCenterIdentity()">Get from blockchain <ion-spinner *ngIf="CIBusy"></ion-spinner></button>\n    </ion-item>\n    <ion-item *ngIf="centerIdentityImportSuccess">\n      <button ion-button primary (click)="getKeyUsingCenterIdentity()" disabled>Success!</button>\n    </ion-item>\n  </ion-list>\n  <h4>Import WIF</h4>\n  <ion-item>\n    <button ion-button secondary (click)="importKey()">Import identity</button>\n  </ion-item>\n</ion-content>\n'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/settings/settings.html"*/
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
            __WEBPACK_IMPORTED_MODULE_16__app_websocket_service__["a" /* WebSocketService */],
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

/***/ 407:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return SiaFiles; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(5);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__app_wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_transaction_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_opengraphparser_service__ = __webpack_require__(140);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_settings_service__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_bulletinSecret_service__ = __webpack_require__(14);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__angular_http__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__app_graph_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__profile_profile__ = __webpack_require__(70);
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
                        var info = {
                            relationship: {
                                my_username_signature: _this.bulletinSecretService.generate_username_signature(),
                                my_username: _this.bulletinSecretService.username
                            },
                            username_signature: _this.group.username_signature,
                            rid: _this.group.rid,
                            requester_rid: _this.group.requester_rid,
                            requested_rid: _this.group.requested_rid
                        };
                        info.relationship[_this.settingsService.collections.GROUP_CHAT] = _this.postText;
                        info.relationship[_this.settingsService.collections.GROUP_CHAT_FILE] = sharefiledata;
                        info.relationship[_this.settingsService.collections.GROUP_CHAT_FILE_NAME] = _this.selectedFile;
                        return _this.transactionService.generateTransaction(info)
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

/***/ 408:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return StreamPage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(5);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__ionic_storage__ = __webpack_require__(48);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_graph_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_bulletinSecret_service__ = __webpack_require__(14);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_transaction_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__app_settings_service__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__angular_http__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__angular_platform_browser__ = __webpack_require__(54);
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
            selector: 'page-stream',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/stream/stream.html"*/'<ion-header>\n    <ion-navbar>\n        <button ion-button menuToggle color="{{color}}">\n            <ion-icon name="menu"></ion-icon>\n        </button>\n        <ion-title>{{label}}</ion-title>\n    </ion-navbar>\n</ion-header>\n<ion-content>\n    <ion-list *ngIf="!error">\n        <button ion-item *ngFor="let group of groups" (click)="selectGroup(group.requested_rid || group.rid)">{{graphService.getIdentityFromTxn(group).username}}</button>\n    </ion-list>\n    <iframe [src]="sanitize(streamUrl)" width="100%" height="100%" border="0" *ngIf="streamUrl && !error" id="iframe"></iframe>\n    <ion-item *ngIf="error">You must download the <a href="https://github.com/pdxwebdev/yadacoin/releases/latest" target="_blank">full node</a> to stream content from the blockchain.</ion-item>\n</ion-content>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/stream/stream.html"*/,
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

/***/ 410:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return MyPagesPage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(5);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__app_bulletinSecret_service__ = __webpack_require__(14);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_graph_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_settings_service__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__buildpage__ = __webpack_require__(234);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__web__ = __webpack_require__(233);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};







var MyPagesPage = /** @class */ (function () {
    function MyPagesPage(navCtrl, navParams, graphService, bulletinSecretService, settingsService) {
        var _this = this;
        this.navCtrl = navCtrl;
        this.navParams = navParams;
        this.graphService = graphService;
        this.bulletinSecretService = bulletinSecretService;
        this.settingsService = settingsService;
        this.items = [];
        this.loading = false;
        this.loading = true;
        var rids = [this.graphService.generateRid(this.bulletinSecretService.identity.username_signature, this.bulletinSecretService.identity.username_signature, this.settingsService.collections.WEB_PAGE)];
        this.graphService.getMyPages(rids)
            .then(function () {
            _this.items = _this.graphService.graph.mypages;
            _this.loading = false;
        });
    }
    MyPagesPage.prototype.itemTapped = function (event, item) {
        var myRids = this.graphService.generateRids(this.bulletinSecretService.identity);
        var recipient;
        if (this.graphService.friends_indexed[item.rid]) {
            recipient = this.graphService.friends_indexed[item.rid].relationship;
        }
        if (myRids.rid == item.rid) {
            recipient = this.bulletinSecretService.identity;
        }
        if (!recipient)
            return;
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_6__web__["a" /* WebPage */], {
            recipient: recipient,
            resource: item.relationship[this.settingsService.collections.WEB_PAGE].resource,
            content: item.relationship[this.settingsService.collections.WEB_PAGE].content
        });
    };
    MyPagesPage.prototype.buildPage = function () {
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_5__buildpage__["a" /* BuildPagePage */]);
    };
    MyPagesPage = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["n" /* Component */])({
            selector: 'mail-mypages',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/web/mypages.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n  </ion-navbar>\n</ion-header>\n<ion-content padding>\n  <ion-refresher (ionRefresh)="refresh($event)">\n    <ion-refresher-content></ion-refresher-content>\n  </ion-refresher>\n  <ion-spinner *ngIf="loading"></ion-spinner>\n  <ion-card *ngIf="items && items.length == 0">\n      <ion-card-content>\n        <ion-card-title style="text-overflow:ellipsis;" text-wrap>\n          No items to display.\n      </ion-card-title>\n    </ion-card-content>\n  </ion-card>\n  <ion-list>\n    <button ion-item *ngFor="let item of items" (click)="itemTapped($event, item)">\n      <ion-item>\n        <div class="resource">{{item.relationship[settingsService.collections.WEB_PAGE].resource}}</div>\n      </ion-item>\n    </button>\n  </ion-list>\n</ion-content>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/web/mypages.html"*/
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["i" /* NavController */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["j" /* NavParams */],
            __WEBPACK_IMPORTED_MODULE_3__app_graph_service__["a" /* GraphService */],
            __WEBPACK_IMPORTED_MODULE_2__app_bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_4__app_settings_service__["a" /* SettingsService */]])
    ], MyPagesPage);
    return MyPagesPage;
}());

//# sourceMappingURL=mypages.js.map

/***/ }),

/***/ 424:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
Object.defineProperty(__webpack_exports__, "__esModule", { value: true });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_platform_browser_dynamic__ = __webpack_require__(425);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__app_module__ = __webpack_require__(535);


Object(__WEBPACK_IMPORTED_MODULE_0__angular_platform_browser_dynamic__["a" /* platformBrowserDynamic */])().bootstrapModule(__WEBPACK_IMPORTED_MODULE_1__app_module__["a" /* AppModule */]);
//# sourceMappingURL=main.js.map

/***/ }),

/***/ 535:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return AppModule; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_platform_browser__ = __webpack_require__(54);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2_ionic_angular__ = __webpack_require__(5);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__angular_http__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__angular_common__ = __webpack_require__(53);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_component__ = __webpack_require__(577);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__pages_home_home__ = __webpack_require__(225);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__pages_home_postmodal__ = __webpack_require__(684);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__pages_list_list__ = __webpack_require__(69);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__pages_settings_settings__ = __webpack_require__(405);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_10__pages_chat_chat__ = __webpack_require__(227);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_11__pages_profile_profile__ = __webpack_require__(70);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_12__pages_siafiles_siafiles__ = __webpack_require__(407);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_13__pages_stream_stream__ = __webpack_require__(408);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_14__pages_mail_mail__ = __webpack_require__(232);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_15__pages_mail_compose__ = __webpack_require__(109);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_16__pages_calendar_calendar__ = __webpack_require__(229);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_17__ionic_native_status_bar__ = __webpack_require__(349);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_18__ionic_native_splash_screen__ = __webpack_require__(352);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_19__ionic_native_qr_scanner__ = __webpack_require__(397);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_20_ngx_qrcode2__ = __webpack_require__(685);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_21__ionic_storage__ = __webpack_require__(48);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_22__graph_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_23__bulletinSecret_service__ = __webpack_require__(14);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_24__peer_service__ = __webpack_require__(226);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_25__settings_service__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_26__wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_27__websocket_service__ = __webpack_require__(37);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_28__transaction_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_29__opengraphparser_service__ = __webpack_require__(140);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_30__firebase_service__ = __webpack_require__(231);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_31__pages_sendreceive_sendreceive__ = __webpack_require__(228);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_32__ionic_native_clipboard__ = __webpack_require__(705);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_33__ionic_native_social_sharing__ = __webpack_require__(108);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_34__ionic_native_badge__ = __webpack_require__(390);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_35__ionic_native_deeplinks__ = __webpack_require__(409);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_36__ionic_native_firebase__ = __webpack_require__(404);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_37__ionic_tools_emoji_picker__ = __webpack_require__(706);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_38__ionic_native_file__ = __webpack_require__(748);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_39_ionic2_auto_complete__ = __webpack_require__(391);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_40__autocomplete_provider__ = __webpack_require__(110);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_41__ionic_native_geolocation__ = __webpack_require__(224);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_42__ionic_native_google_maps__ = __webpack_require__(406);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_43__pages_mail_mailitem__ = __webpack_require__(138);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_44__pages_signaturerequest_signaturerequest__ = __webpack_require__(398);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_45__pages_web_web__ = __webpack_require__(233);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_46__pages_web_mypages__ = __webpack_require__(410);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_47__pages_web_buildpage__ = __webpack_require__(234);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_48_ionic_tooltips__ = __webpack_require__(749);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_49__angular_platform_browser_animations__ = __webpack_require__(751);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_50__pages_assets_assets__ = __webpack_require__(230);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_51__pages_assets_assetitem__ = __webpack_require__(401);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_52__pages_assets_createasset__ = __webpack_require__(400);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_53__smartContract_service__ = __webpack_require__(68);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_54__pages_markets_market__ = __webpack_require__(399);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_55__pages_markets_marketitem__ = __webpack_require__(139);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_56__pages_markets_createsale__ = __webpack_require__(402);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_57__pages_markets_createpromo__ = __webpack_require__(403);
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
                __WEBPACK_IMPORTED_MODULE_12__pages_siafiles_siafiles__["a" /* SiaFiles */],
                __WEBPACK_IMPORTED_MODULE_13__pages_stream_stream__["a" /* StreamPage */],
                __WEBPACK_IMPORTED_MODULE_14__pages_mail_mail__["a" /* MailPage */],
                __WEBPACK_IMPORTED_MODULE_15__pages_mail_compose__["a" /* ComposePage */],
                __WEBPACK_IMPORTED_MODULE_16__pages_calendar_calendar__["a" /* CalendarPage */],
                __WEBPACK_IMPORTED_MODULE_43__pages_mail_mailitem__["a" /* MailItemPage */],
                __WEBPACK_IMPORTED_MODULE_44__pages_signaturerequest_signaturerequest__["a" /* SignatureRequestPage */],
                __WEBPACK_IMPORTED_MODULE_45__pages_web_web__["a" /* WebPage */],
                __WEBPACK_IMPORTED_MODULE_46__pages_web_mypages__["a" /* MyPagesPage */],
                __WEBPACK_IMPORTED_MODULE_47__pages_web_buildpage__["a" /* BuildPagePage */],
                __WEBPACK_IMPORTED_MODULE_50__pages_assets_assets__["a" /* AssetsPage */],
                __WEBPACK_IMPORTED_MODULE_51__pages_assets_assetitem__["a" /* AssetItemPage */],
                __WEBPACK_IMPORTED_MODULE_54__pages_markets_market__["a" /* MarketPage */],
                __WEBPACK_IMPORTED_MODULE_55__pages_markets_marketitem__["a" /* MarketItemPage */],
                __WEBPACK_IMPORTED_MODULE_52__pages_assets_createasset__["a" /* CreateAssetPage */],
                __WEBPACK_IMPORTED_MODULE_56__pages_markets_createsale__["a" /* CreateSalePage */],
                __WEBPACK_IMPORTED_MODULE_57__pages_markets_createpromo__["a" /* CreatePromoPage */]
            ],
            imports: [
                __WEBPACK_IMPORTED_MODULE_0__angular_platform_browser__["a" /* BrowserModule */],
                __WEBPACK_IMPORTED_MODULE_39_ionic2_auto_complete__["b" /* AutoCompleteModule */],
                __WEBPACK_IMPORTED_MODULE_2_ionic_angular__["e" /* IonicModule */].forRoot(__WEBPACK_IMPORTED_MODULE_5__app_component__["a" /* MyApp */], {}, {
                    links: []
                }),
                __WEBPACK_IMPORTED_MODULE_21__ionic_storage__["a" /* IonicStorageModule */].forRoot({
                    name: '__mydb',
                    driverOrder: ['websql', 'sqlite', 'indexeddb']
                }),
                __WEBPACK_IMPORTED_MODULE_20_ngx_qrcode2__["a" /* NgxQRCodeModule */],
                __WEBPACK_IMPORTED_MODULE_3__angular_http__["c" /* HttpModule */],
                __WEBPACK_IMPORTED_MODULE_37__ionic_tools_emoji_picker__["a" /* EmojiPickerModule */].forRoot(),
                __WEBPACK_IMPORTED_MODULE_4__angular_common__["b" /* CommonModule */],
                __WEBPACK_IMPORTED_MODULE_48_ionic_tooltips__["a" /* TooltipsModule */].forRoot(),
                __WEBPACK_IMPORTED_MODULE_49__angular_platform_browser_animations__["a" /* BrowserAnimationsModule */]
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
                __WEBPACK_IMPORTED_MODULE_12__pages_siafiles_siafiles__["a" /* SiaFiles */],
                __WEBPACK_IMPORTED_MODULE_13__pages_stream_stream__["a" /* StreamPage */],
                __WEBPACK_IMPORTED_MODULE_14__pages_mail_mail__["a" /* MailPage */],
                __WEBPACK_IMPORTED_MODULE_15__pages_mail_compose__["a" /* ComposePage */],
                __WEBPACK_IMPORTED_MODULE_16__pages_calendar_calendar__["a" /* CalendarPage */],
                __WEBPACK_IMPORTED_MODULE_43__pages_mail_mailitem__["a" /* MailItemPage */],
                __WEBPACK_IMPORTED_MODULE_44__pages_signaturerequest_signaturerequest__["a" /* SignatureRequestPage */],
                __WEBPACK_IMPORTED_MODULE_45__pages_web_web__["a" /* WebPage */],
                __WEBPACK_IMPORTED_MODULE_46__pages_web_mypages__["a" /* MyPagesPage */],
                __WEBPACK_IMPORTED_MODULE_47__pages_web_buildpage__["a" /* BuildPagePage */],
                __WEBPACK_IMPORTED_MODULE_50__pages_assets_assets__["a" /* AssetsPage */],
                __WEBPACK_IMPORTED_MODULE_51__pages_assets_assetitem__["a" /* AssetItemPage */],
                __WEBPACK_IMPORTED_MODULE_54__pages_markets_market__["a" /* MarketPage */],
                __WEBPACK_IMPORTED_MODULE_55__pages_markets_marketitem__["a" /* MarketItemPage */],
                __WEBPACK_IMPORTED_MODULE_52__pages_assets_createasset__["a" /* CreateAssetPage */],
                __WEBPACK_IMPORTED_MODULE_56__pages_markets_createsale__["a" /* CreateSalePage */],
                __WEBPACK_IMPORTED_MODULE_57__pages_markets_createpromo__["a" /* CreatePromoPage */]
            ],
            providers: [
                __WEBPACK_IMPORTED_MODULE_17__ionic_native_status_bar__["a" /* StatusBar */],
                __WEBPACK_IMPORTED_MODULE_18__ionic_native_splash_screen__["a" /* SplashScreen */],
                { provide: __WEBPACK_IMPORTED_MODULE_1__angular_core__["v" /* ErrorHandler */], useClass: __WEBPACK_IMPORTED_MODULE_2_ionic_angular__["d" /* IonicErrorHandler */] },
                __WEBPACK_IMPORTED_MODULE_19__ionic_native_qr_scanner__["a" /* QRScanner */],
                __WEBPACK_IMPORTED_MODULE_20_ngx_qrcode2__["a" /* NgxQRCodeModule */],
                __WEBPACK_IMPORTED_MODULE_22__graph_service__["a" /* GraphService */],
                __WEBPACK_IMPORTED_MODULE_23__bulletinSecret_service__["a" /* BulletinSecretService */],
                __WEBPACK_IMPORTED_MODULE_24__peer_service__["a" /* PeerService */],
                __WEBPACK_IMPORTED_MODULE_25__settings_service__["a" /* SettingsService */],
                __WEBPACK_IMPORTED_MODULE_26__wallet_service__["a" /* WalletService */],
                __WEBPACK_IMPORTED_MODULE_27__websocket_service__["a" /* WebSocketService */],
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
                __WEBPACK_IMPORTED_MODULE_42__ionic_native_google_maps__["a" /* GoogleMaps */],
                __WEBPACK_IMPORTED_MODULE_53__smartContract_service__["a" /* SmartContractService */]
            ]
        })
    ], AppModule);
    return AppModule;
}());

//# sourceMappingURL=app.module.js.map

/***/ }),

/***/ 577:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return MyApp; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(5);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__ionic_native_status_bar__ = __webpack_require__(349);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__ionic_native_splash_screen__ = __webpack_require__(352);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__graph_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__settings_service__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__bulletinSecret_service__ = __webpack_require__(14);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__pages_home_home__ = __webpack_require__(225);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__pages_list_list__ = __webpack_require__(69);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_10__pages_calendar_calendar__ = __webpack_require__(229);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_11__pages_settings_settings__ = __webpack_require__(405);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_12__pages_siafiles_siafiles__ = __webpack_require__(407);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_13__pages_stream_stream__ = __webpack_require__(408);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_14__pages_sendreceive_sendreceive__ = __webpack_require__(228);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_15__pages_mail_mail__ = __webpack_require__(232);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_16__ionic_native_deeplinks__ = __webpack_require__(409);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_17__websocket_service__ = __webpack_require__(37);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_18__pages_web_web__ = __webpack_require__(233);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_19__pages_web_mypages__ = __webpack_require__(410);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_20__pages_web_buildpage__ = __webpack_require__(234);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_21__pages_assets_assets__ = __webpack_require__(230);
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
    function MyApp(platform, statusBar, splashScreen, walletService, websocketService, graphService, settingsService, bulletinSecretService, events, deeplinks) {
        var _this = this;
        this.platform = platform;
        this.statusBar = statusBar;
        this.splashScreen = splashScreen;
        this.walletService = walletService;
        this.websocketService = websocketService;
        this.graphService = graphService;
        this.settingsService = settingsService;
        this.bulletinSecretService = bulletinSecretService;
        this.events = events;
        this.deeplinks = deeplinks;
        events.subscribe('graph', function () {
            _this.rootPage = __WEBPACK_IMPORTED_MODULE_8__pages_home_home__["a" /* HomePage */];
        });
        events.subscribe('menu', function (options) {
            _this.setMenu(options);
            if (!_this.pages)
                return;
            if (_this.pages.length === 0)
                return;
            _this.root = _this.pages[0].root;
            _this.openPage(_this.pages[0]);
        });
        events.subscribe('menuonly', function (options) {
            _this.setMenu(options);
            _this.root = _this.pages[0].root;
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
        if (this.settingsService.menu === 'home') {
            this.pages = [
                { title: 'Home', label: 'Home', component: __WEBPACK_IMPORTED_MODULE_8__pages_home_home__["a" /* HomePage */], count: false, color: '', root: true },
            ];
        }
        else if (this.settingsService.menu === 'mail') {
            this.pages = [
                { title: 'Inbox', label: 'Inbox', component: __WEBPACK_IMPORTED_MODULE_15__pages_mail_mail__["a" /* MailPage */], count: false, color: '', root: true },
                { title: 'Sent', label: 'Sent', component: __WEBPACK_IMPORTED_MODULE_15__pages_mail_mail__["a" /* MailPage */], count: false, color: '', root: true },
            ];
        }
        else if (this.settingsService.menu === 'chat') {
            this.graphService.getMessagesForAllFriendsAndGroups();
            this.pages = [
                { title: 'Messages', label: 'Chat', component: __WEBPACK_IMPORTED_MODULE_9__pages_list_list__["a" /* ListPage */], count: false, color: '', root: true },
            ];
        }
        else if (this.settingsService.menu === 'community') {
            this.graphService.getMessagesForAllFriendsAndGroups();
            this.pages = [
                { title: 'Community', label: 'Community', component: __WEBPACK_IMPORTED_MODULE_9__pages_list_list__["a" /* ListPage */], count: false, color: '', root: true },
            ];
        }
        else if (this.settingsService.menu === 'calendar') {
            this.pages = [
                { title: 'Calendar', label: 'Calendar', component: __WEBPACK_IMPORTED_MODULE_10__pages_calendar_calendar__["a" /* CalendarPage */], count: false, color: '', root: true },
            ];
        }
        else if (this.settingsService.menu === 'contacts') {
            this.pages = [
                { title: 'Contacts', label: 'Contacts', component: __WEBPACK_IMPORTED_MODULE_9__pages_list_list__["a" /* ListPage */], count: false, color: '', root: true },
                { title: 'Contact Requests', label: 'Contact Requests', component: __WEBPACK_IMPORTED_MODULE_9__pages_list_list__["a" /* ListPage */], count: false, color: '', root: true },
                { title: 'Groups', label: 'Groups', component: __WEBPACK_IMPORTED_MODULE_9__pages_list_list__["a" /* ListPage */], count: false, color: '', root: true },
            ];
        }
        else if (this.settingsService.menu === 'assets') {
            this.pages = [
                { title: 'Assets', label: 'Assets', component: __WEBPACK_IMPORTED_MODULE_21__pages_assets_assets__["a" /* AssetsPage */], count: false, color: '', root: true },
            ];
        }
        else if (this.settingsService.menu === 'markets') {
            this.pages = [
                { title: 'Markets', label: 'Markets', component: __WEBPACK_IMPORTED_MODULE_9__pages_list_list__["a" /* ListPage */], count: false, color: '', root: true },
            ];
        }
        else if (this.settingsService.menu === 'affiliates') {
            this.pages = [
                { title: 'Affiliates', label: 'Affiliates', component: __WEBPACK_IMPORTED_MODULE_9__pages_list_list__["a" /* ListPage */], count: false, color: '', root: true },
            ];
        }
        else if (this.settingsService.menu === 'files') {
            this.pages = [
                { title: 'Files', label: 'Files', component: __WEBPACK_IMPORTED_MODULE_12__pages_siafiles_siafiles__["a" /* SiaFiles */], count: false, color: '', root: true },
            ];
        }
        else if (this.settingsService.menu === 'wallet') {
            this.pages = [
                { title: 'Send / Receive', label: 'Send / Receive', component: __WEBPACK_IMPORTED_MODULE_14__pages_sendreceive_sendreceive__["a" /* SendReceive */], count: false, color: '', root: true }
            ];
        }
        else if (this.settingsService.menu === 'stream') {
            this.pages = [
                { title: 'Stream', label: 'Stream', component: __WEBPACK_IMPORTED_MODULE_13__pages_stream_stream__["a" /* StreamPage */], count: false, color: '', root: true }
            ];
        }
        else if (this.settingsService.menu === 'settings') {
            this.pages = [
                { title: 'Settings', label: 'Identity', component: __WEBPACK_IMPORTED_MODULE_11__pages_settings_settings__["a" /* Settings */], count: false, color: '', root: true },
            ];
        }
        else if (this.settingsService.menu === 'notifications') {
            this.pages = [
                { title: 'Notifications', label: 'Notifications', component: __WEBPACK_IMPORTED_MODULE_9__pages_list_list__["a" /* ListPage */], count: false, color: '', root: true },
            ];
        }
        else if (this.settingsService.menu === 'web') {
            this.pages = [
                { title: 'Web', label: 'Web', component: __WEBPACK_IMPORTED_MODULE_18__pages_web_web__["a" /* WebPage */], count: false, color: '', root: true },
                { title: 'Create page', label: 'Create page', component: __WEBPACK_IMPORTED_MODULE_20__pages_web_buildpage__["a" /* BuildPagePage */], count: false, color: '', root: true },
                { title: 'My pages', label: 'My pages', component: __WEBPACK_IMPORTED_MODULE_19__pages_web_mypages__["a" /* MyPagesPage */], count: false, color: '', root: true },
            ];
        }
    };
    MyApp.prototype.initializeApp = function () {
        var _this = this;
        this.platform.ready()
            .then(function () {
            if (_this.platform.is('cordova')) {
                _this.deeplinks.routeWithNavController(_this.nav, {}).subscribe(function (match) {
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
        this.settingsService.menu = e.currentTarget.value;
        this.setMenu();
        this.root = this.pages[0].root;
        this.openPage(this.pages[0]);
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
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["n" /* Component */])({template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/app/app.html"*/'<ion-split-pane>\n  <ion-menu [content]="content">\n    <ion-header>\n      <ion-toolbar>\n        <ion-title>\n          <ion-note *ngIf="settingsService.remoteSettings.restricted" style="font-size: 20px">\n            {{bulletinSecretService.identity.username || \'Center Identity\'}}\n          </ion-note>\n          <ion-note *ngIf="!settingsService.remoteSettings.restricted" style="font-size: 20px">\n            {{bulletinSecretService.identity.username || \'YadaCoin\'}}\n          </ion-note>\n          <ion-note style="font-size: 12px">\n            {{version}}\n          </ion-note>\n        </ion-title>\n      </ion-toolbar>\n    </ion-header>\n\n    <ion-content *ngIf="bulletinSecretService.key">\n      <ion-row>\n        <ion-col col-lg-2 col-md-2 col-sm-2>\n          <button\n            class="navbutton"\n            [color]="settingsService.menu === \'home\' ? \'secondary\' : \'primary\'"\n            ion-button\n            value="home"\n            tooltip="Home"\n            (click)="segmentChanged($event)"\n            icon-only\n            navTooltip\n            arrow="true"\n            positionH="right"\n            topOffset="-67"\n          >\n            <ion-icon name="home"></ion-icon>\n          </button>\n          <button\n            class="navbutton"\n            [color]="settingsService.menu === \'wallet\' ? \'secondary\' : \'primary\'"\n            ion-button\n            value="wallet"\n            tooltip="Wallet"\n            (click)="segmentChanged($event)"\n            icon-only\n            navTooltip\n            arrow="true"\n            positionH="right"\n            topOffset="-67"\n          >\n            <ion-icon name="cash"></ion-icon>\n          </button>\n          <button\n            class="navbutton"\n            [color]="settingsService.menu === \'mail\' ? \'secondary\' : \'primary\'"\n            ion-button\n            value="mail"\n            tooltip="Mail"\n            (click)="segmentChanged($event)"\n            icon-only\n            navTooltip\n            arrow="true"\n            positionH="right"\n            topOffset="-67"\n          >\n            <ion-icon name="mail"></ion-icon>\n            <ion-badge\n              *ngIf="graphService.notifications[settingsService.collections.MAIL]?.length > 0 || graphService.notifications[settingsService.collections.GROUP_MAIL]?.length > 0"\n              color="secondary"\n              style="vertical-align:top;position:absolute;"\n              item-right\n            >{{graphService.notifications[settingsService.collections.MAIL].length + graphService.notifications[settingsService.collections.GROUP_MAIL].length}}</ion-badge>\n          </button>\n          <button\n            class="navbutton"\n            [color]="settingsService.menu === \'chat\' ? \'secondary\' : \'primary\'"\n            ion-button\n            value="chat"\n            tooltip="Private messages"\n            (click)="segmentChanged($event)"\n            icon-only\n            navTooltip\n            arrow="true"\n            positionH="right"\n            topOffset="-67"\n          >\n            <ion-icon name="chatboxes"></ion-icon>\n            <ion-badge\n              *ngIf="graphService.notifications[settingsService.collections.CHAT]?.length > 0"\n              color="secondary"\n              style="vertical-align:top;position:absolute;"\n              item-right\n            >{{graphService.notifications[settingsService.collections.CHAT].length}}</ion-badge>\n          </button>\n          <button\n            class="navbutton"\n            [color]="settingsService.menu === \'community\' ? \'secondary\' : \'primary\'"\n            ion-button\n            value="community"\n            tooltip="Community chat"\n            (click)="segmentChanged($event)"\n            icon-only\n            navTooltip\n            arrow="true"\n            positionH="right"\n            topOffset="-67"\n          >\n            <ion-icon name="chatbubbles"></ion-icon>\n            <ion-badge\n              *ngIf="graphService.notifications[settingsService.collections.GROUP_CHAT]?.length > 0"\n              color="secondary"\n              style="vertical-align:top;position:absolute;"\n              item-right\n            >{{graphService.notifications[settingsService.collections.GROUP_CHAT].length}}</ion-badge>\n          </button>\n          <button\n            class="navbutton"\n            [color]="settingsService.menu === \'calendar\' ? \'secondary\' : \'primary\'"\n            ion-button\n            value="calendar"\n            tooltip="Calendar"\n            (click)="segmentChanged($event)"\n            icon-only\n            navTooltip\n            arrow="true"\n            positionH="right"\n            topOffset="-67"\n          >\n            <ion-icon name="calendar"></ion-icon>\n            <ion-badge\n              *ngIf="graphService.notifications[settingsService.collections.CALENDAR]?.length > 0 || graphService.notifications[settingsService.collections.GROUP_CALENDAR]?.length > 0"\n              color="secondary"\n              style="vertical-align:top;position:absolute;"\n              item-right\n            >{{graphService.notifications[settingsService.collections.CALENDAR].length + graphService.notifications[settingsService.collections.GROUP_CALENDAR].length}}</ion-badge>\n          </button>\n          <button\n            class="navbutton"\n            [color]="settingsService.menu === \'contacts\' ? \'secondary\' : \'primary\'"\n            ion-button\n            value="contacts"\n            tooltip="Contacts"\n            (click)="segmentChanged($event)"\n            icon-only\n            navTooltip\n            arrow="true"\n            positionH="right"\n            topOffset="-67"\n          >\n            <ion-icon name="contacts"></ion-icon>\n            <ion-badge\n              *ngIf="graphService.notifications[settingsService.collections.CONTACT]?.length > 0"\n              color="secondary"\n              style="vertical-align:top;position:absolute;"\n              item-right\n            >{{graphService.notifications[settingsService.collections.CONTACT].length}}</ion-badge>\n          </button>\n          <button\n            class="navbutton"\n            [color]="settingsService.menu === \'files\' ? \'secondary\' : \'primary\'"\n            ion-button\n            value="files"\n            tooltip="Files"\n            (click)="segmentChanged($event)"\n            *ngIf="settingsService.remoteSettings.restricted"\n            icon-only\n            navTooltip\n            arrow="true"\n            positionH="right"\n            topOffset="-67"\n          >\n            <ion-icon name="folder"></ion-icon>\n          </button>\n          <button\n            class="navbutton"\n            [color]="settingsService.menu === \'assets\' ? \'secondary\' : \'primary\'"\n            ion-button\n            value="assets"\n            tooltip="Assets"\n            (click)="segmentChanged($event)"\n            *ngIf="!settingsService.remoteSettings.restricted"\n            icon-only\n            navTooltip\n            arrow="true"\n            positionH="right"\n            topOffset="-67"\n          >\n            <ion-icon name="pricetag"></ion-icon>\n          </button>\n          <button\n            class="navbutton"\n            [color]="settingsService.menu === \'markets\' ? \'secondary\' : \'primary\'"\n            ion-button\n            value="markets"\n            tooltip="Markets"\n            (click)="segmentChanged($event)"\n            icon-only\n            navTooltip\n            arrow="true"\n            positionH="right"\n            topOffset="-67"\n          >\n            <ion-icon name="cart"></ion-icon>\n            <ion-badge\n              *ngIf="graphService.notifications[settingsService.collections.MARKET]?.length > 0"\n              color="secondary"\n              style="vertical-align:top;position:absolute;"\n              item-right\n            >{{graphService.notifications[settingsService.collections.MARKET].length}}</ion-badge>\n          </button>\n          <!-- <button\n            class="navbutton"\n            [color]="settingsService.menu === \'web\' ? \'secondary\' : \'primary\'"\n            ion-button\n            value="web"\n            tooltip="Web"\n            (click)="segmentChanged($event)"\n            icon-only\n            navTooltip\n            arrow="true"\n            positionH="right"\n            topOffset="-67"\n          >\n            <ion-icon name="globe"></ion-icon>\n          </button> -->\n          <button\n            class="navbutton"\n            [color]="settingsService.menu === \'notifications\' ? \'secondary\' : \'primary\'"\n            ion-button\n            value="notifications"\n            tooltip="Notifications"\n            (click)="segmentChanged($event)"\n            icon-only\n            navTooltip\n            arrow="true"\n            positionH="right"\n            topOffset="-67"\n          >\n            <ion-icon name="notifications"></ion-icon>\n            <ion-badge\n              *ngIf="graphService.notifications[\'notifications\']?.length > 0"\n              color="secondary"\n              style="vertical-align:top;position:absolute;"\n              item-right\n            >{{graphService.notifications[\'notifications\'].length}}</ion-badge>\n          </button>\n          <button\n            class="navbutton"\n            [color]="settingsService.menu === \'settings\' ? \'secondary\' : \'primary\'"\n            ion-button\n            value="settings"\n            tooltip="Identity"\n            (click)="segmentChanged($event)"\n            icon-only\n            navTooltip\n            arrow="true"\n            positionH="right"\n            topOffset="-67"\n          >\n            <ion-icon name="contact"></ion-icon>\n          </button>\n        </ion-col>\n        <ion-col col-lg-10 col-md-10 col-sm-10 style="padding-right: 7px; margin-top: 4px;">\n          <ng-container *ngFor="let p of pages">\n            <button\n              menuClose\n              ion-item\n              (click)="openPage(p)"\n              [color]="\'grey\'"\n              *ngIf="p.title == \'Contact Requests\'"\n              class="subnavbutton"\n            >\n              {{p.label}} <ion-note *ngIf="graphService.graph.friend_requests">{{graphService.graph.friend_requests.length}}</ion-note>\n            </button>\n            <button\n              menuClose\n              ion-item\n              (click)="openPage(p)"\n              [color]="\'grey\'"\n              *ngIf="p.title == \'Messages\'"\n              class="subnavbutton"\n            >\n              {{p.label}}\n            </button>\n            <button\n              menuClose\n              ion-item\n              (click)="openPage(p)"\n              *ngIf="[\'Messages\', \'Contact Requests\'].indexOf(p.title) < 0"\n              class="subnavbutton"\n            >\n              {{p.label}} <ion-note *ngIf="p.kwargs && p.kwargs.identity && graphService.counts[p.kwargs.identity.username_signature] && graphService.counts[p.kwargs.identity.username_signature] > 0">{{graphService.counts[p.kwargs.identity.username_signature]}}</ion-note>\n            </button>\n            <ng-container *ngIf="p.kwargs && p.kwargs.identity && p.kwargs.subitems && p.kwargs.subitems[p.kwargs.identity.username_signature]">\n              <button\n                menuClose\n                ion-item\n                (click)="openPage(subitem)"\n                class="subnavbutton"\n                *ngFor="let subitem of p.kwargs.subitems[p.kwargs.identity.username_signature]"\n              >\n                &nbsp;&nbsp;&nbsp;&nbsp;{{subitem.kwargs.identity.username}} <ion-note *ngIf="graphService.counts[subitem.kwargs.identity.username_signature] && graphService.counts[subitem.kwargs.identity.username_signature] > 0">{{graphService.counts[subitem.kwargs.identity.username_signature]}}</ion-note>\n              </button>\n            </ng-container>\n          </ng-container>\n        </ion-col>\n      </ion-row>\n      <img *ngIf="!settingsService.remoteSettings.restricted" src="assets/img/yadacoinlogosmall.png" class="logo">\n      <img *ngIf="settingsService.remoteSettings.restricted" src="assets/center-identity-logo-square.png" class="logo">\n    </ion-content>\n  </ion-menu>\n  <!-- Disable swipe-to-go-back because it\'s poor UX to combine STGB with side menus -->\n  <ion-nav [root]="rootPage" main #content swipeBackEnabled="false"></ion-nav>\n</ion-split-pane>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/app/app.html"*/
        }),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1_ionic_angular__["k" /* Platform */],
            __WEBPACK_IMPORTED_MODULE_2__ionic_native_status_bar__["a" /* StatusBar */],
            __WEBPACK_IMPORTED_MODULE_3__ionic_native_splash_screen__["a" /* SplashScreen */],
            __WEBPACK_IMPORTED_MODULE_7__wallet_service__["a" /* WalletService */],
            __WEBPACK_IMPORTED_MODULE_17__websocket_service__["a" /* WebSocketService */],
            __WEBPACK_IMPORTED_MODULE_4__graph_service__["a" /* GraphService */],
            __WEBPACK_IMPORTED_MODULE_5__settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_6__bulletinSecret_service__["a" /* BulletinSecretService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["b" /* Events */],
            __WEBPACK_IMPORTED_MODULE_16__ionic_native_deeplinks__["a" /* Deeplinks */]])
    ], MyApp);
    return MyApp;
}());

//# sourceMappingURL=app.component.js.map

/***/ }),

/***/ 623:
/***/ (function(module, exports) {

/* (ignored) */

/***/ }),

/***/ 624:
/***/ (function(module, exports) {

/* (ignored) */

/***/ }),

/***/ 68:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return SmartContractService; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1__settings_service__ = __webpack_require__(10);
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};


var SmartContractService = /** @class */ (function () {
    function SmartContractService(settingsService) {
        this.settingsService = settingsService;
        this.version = 1;
        this.payoutOperators = {
            PERCENT: 'percent',
            FIXED: 'fixed'
        };
        this.payoutType = {
            RECURRING: 'recurring',
            ONE_TIME: 'one_time'
        };
        this.assetProofTypes = {
            CONFIRMATION: 'confirmation',
            FIRST_COME: 'first_come',
            AUCTION: 'auction'
        };
        this.promoProofTypes = {
            COINBASE: 'coinbase',
            CONFIRMATION: 'confirmation',
            HONOR: 'honor'
        };
        this.contractTypes = {
            CHANGE_OWNERSHIP: 'change_ownership',
            NEW_RELATIONSHIP: 'new_relationship'
        };
    }
    SmartContractService.prototype.generateChangeOfOwnership = function (asset, creator, amount, proof_type, market, contract_expiry) {
        var key = foobar.bitcoin.ECPair.makeRandom();
        var wif = key.toWIF();
        var username = '';
        var username_signature = foobar.base64.fromByteArray(key.sign(foobar.bitcoin.crypto.sha256(username)).toDER());
        var public_key = key.getPublicKeyBuffer().toString('hex');
        var identity = {
            username: username,
            username_signature: username_signature,
            public_key: public_key,
            wif: wif,
            collection: this.settingsService.collections.SMART_CONTRACT
        };
        var expiry = parseInt(contract_expiry) + parseInt(this.settingsService.latest_block.height);
        var contract_type = this.contractTypes.CHANGE_OWNERSHIP;
        var payout_amount = 1;
        var payout_operator = this.payoutOperators.PERCENT;
        var payout_type = this.payoutType.ONE_TIME;
        var price = amount;
        var username_signatures = [market.username_signature, market.username_signature].sort(function (a, b) {
            return a.toLowerCase().localeCompare(b.toLowerCase());
        });
        var market_rid = forge.sha256.create().update(username_signatures[0] + username_signatures[1] + this.settingsService.collections.MARKET).digest().toHex();
        return {
            version: this.version,
            expiry: expiry,
            contract_type: contract_type,
            payout_amount: payout_amount,
            payout_operator: payout_operator,
            payout_type: payout_type,
            proof_type: proof_type,
            price: price,
            identity: identity,
            asset: asset,
            creator: creator,
            market: market_rid
        };
    };
    SmartContractService.prototype.generateNewRelationshipPromo = function (creator, proof_type, target, market, pay_referrer, pay_referrer_operator, pay_referrer_payout_type, pay_referrer_payout_interval, pay_referrer_amount, pay_referee, pay_referee_operator, pay_referee_payout_type, pay_referee_payout_interval, pay_referee_amount, contract_expiry) {
        var key = foobar.bitcoin.ECPair.makeRandom();
        var wif = key.toWIF();
        var username = '';
        var username_signature = foobar.base64.fromByteArray(key.sign(foobar.bitcoin.crypto.sha256(username)).toDER());
        var public_key = key.getPublicKeyBuffer().toString('hex');
        var identity = {
            username: username,
            username_signature: username_signature,
            public_key: public_key,
            wif: wif,
            collection: this.settingsService.collections.SMART_CONTRACT
        };
        var expiry = parseInt(contract_expiry) + parseInt(this.settingsService.latest_block.height);
        var contract_type = this.contractTypes.NEW_RELATIONSHIP;
        var username_signatures = [market.username_signature, market.username_signature].sort(function (a, b) {
            return a.toLowerCase().localeCompare(b.toLowerCase());
        });
        var market_rid = forge.sha256.create().update(username_signatures[0] + username_signatures[1] + this.settingsService.collections.MARKET).digest().toHex();
        return {
            version: this.version,
            expiry: expiry,
            contract_type: contract_type,
            proof_type: proof_type,
            identity: identity,
            creator: creator,
            target: target,
            market: market_rid,
            referrer: {
                active: pay_referrer,
                operator: pay_referrer_operator,
                payout_type: pay_referrer_payout_type,
                amount: pay_referrer_amount,
                interval: pay_referrer_payout_interval || ''
            },
            referee: {
                active: pay_referee,
                operator: pay_referee_operator,
                payout_type: pay_referee_payout_type,
                amount: pay_referee_amount,
                interval: pay_referee_payout_interval || ''
            }
        };
    };
    SmartContractService.prototype.toString = function (contract) {
        if (contract.contract_type === this.contractTypes.CHANGE_OWNERSHIP) {
            return ('' +
                contract.version +
                contract.expiry +
                contract.contract_type +
                contract.payout_amount.toFixed(8) +
                contract.payout_operator +
                contract.payout_type +
                contract.market +
                contract.proof_type +
                contract.price.toFixed(8) +
                contract.identity.username_signature +
                contract.asset +
                contract.creator);
        }
        else if (contract.contract_type === this.contractTypes.NEW_RELATIONSHIP) {
            var referrer_str = contract.referrer.active === true ? ('true' +
                contract.referrer.operator +
                contract.referrer.payout_type +
                contract.referrer.interval +
                contract.referrer.amount.toFixed(8)) : 'false';
            var referee_str = contract.referee.active === true ? ('true' +
                contract.referee.operator +
                contract.referee.payout_type +
                contract.referee.interval +
                contract.referee.amount.toFixed(8)) : 'false';
            return ('' +
                contract.version +
                contract.expiry +
                contract.contract_type +
                contract.proof_type +
                contract.target +
                contract.market +
                contract.identity.username_signature +
                referrer_str +
                referee_str +
                contract.creator);
        }
    };
    SmartContractService = __decorate([
        Object(__WEBPACK_IMPORTED_MODULE_0__angular_core__["B" /* Injectable */])(),
        __metadata("design:paramtypes", [__WEBPACK_IMPORTED_MODULE_1__settings_service__["a" /* SettingsService */]])
    ], SmartContractService);
    return SmartContractService;
}());

//# sourceMappingURL=smartContract.service.js.map

/***/ }),

/***/ 683:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony default export */ __webpack_exports__["a"] = ({
    default_groups: [
        {
            "username": "Text Channels",
            "username_signature": "MEQCIE29etn0ZKakmbuI7uaSLwf7O+W3fyX9HDtGSZspagknAiBKfSM2H8/T/b9mIxvzDIjh05nw0V7nrN22/+pcArlj6w==",
            "public_key": "025879ebd9760913bca9d2a95dd5d1dd2d258995f176985d285ed1c824b391e039",
            "collection": "group"
        },
        {
            "username": "Yada Protocol",
            "username_signature": "MEQCIAZ0wJYLDxJei2Za7XMzbx+AOqeH2PpB6suzTF/bvqgkAiBJYnznzkNlfqjY+1bRUnn5bIuIxL0wz2Mi/TB81487rA==",
            "public_key": "025879ebd9760913bca9d2a95dd5d1dd2d258995f176985d285ed1c824b391e039",
            "collection": "group"
        },
        {
            "username": "Yada App",
            "username_signature": "MEUCIQCa091+XlEyJ4w44Az4xFLySEvzf8WS7nv3qVmAj0L7bgIgaSkLRBCDHt/MIfmlNDN7UsnGYc+9HitPMgsCEZDG4xY=",
            "public_key": "025879ebd9760913bca9d2a95dd5d1dd2d258995f176985d285ed1c824b391e039",
            "collection": "group"
        },
        {
            "username": "YadaCoin",
            "username_signature": "MEQCIDMpt/iX+l60D3ZpANgib973gxwxMwMXoEZ2BF/6A5U6AiBHM1GyMQORffO/YM8dG386/2PBTHCYd0YZu+GaWt5Geg==",
            "public_key": "025879ebd9760913bca9d2a95dd5d1dd2d258995f176985d285ed1c824b391e039",
            "collection": "group"
        },
    ],
    default_markets: [
        {
            "username": "Marketplace",
            "username_signature": "MEUCIQDkV0OjvBtW5g6Hm7OtplD4AkeFcCUBT+UaMMTwYggARAIgK74HoNW5WD7uHpTZPv6WieE1igEgTva7kcmxJm/H6Wc=",
            "public_key": "025879ebd9760913bca9d2a95dd5d1dd2d258995f176985d285ed1c824b391e039",
            "collection": "market"
        },
        {
            "username": "Promotions",
            "username_signature": "MEQCIHF50YImuU7az7tAn5MbM3Z+1YN6gN/zEPretnSLdJ3XAiBMTv1DN+TL4strit+PORmgw2xSk52zKzHjpdB2yfxjJg==",
            "public_key": "025879ebd9760913bca9d2a95dd5d1dd2d258995f176985d285ed1c824b391e039",
            "collection": "market"
        },
    ]
});
//# sourceMappingURL=groups.js.map

/***/ }),

/***/ 684:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return PostModal; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(5);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__app_wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_transaction_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_opengraphparser_service__ = __webpack_require__(140);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_settings_service__ = __webpack_require__(10);
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

/***/ 69:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return ListPage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(5);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__ionic_storage__ = __webpack_require__(48);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_graph_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_bulletinSecret_service__ = __webpack_require__(14);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_transaction_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__app_settings_service__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__ionic_native_social_sharing__ = __webpack_require__(108);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__chat_chat__ = __webpack_require__(227);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_10__profile_profile__ = __webpack_require__(70);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_11__signaturerequest_signaturerequest__ = __webpack_require__(398);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_12__angular_http__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_13__mail_mailitem__ = __webpack_require__(138);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_14__app_websocket_service__ = __webpack_require__(37);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_15__calendar_calendar__ = __webpack_require__(229);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_16__markets_market__ = __webpack_require__(399);
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
    function ListPage(navCtrl, navParams, storage, graphService, bulletinSecretService, walletService, transactionService, socialSharing, alertCtrl, loadingCtrl, events, ahttp, settingsService, toastCtrl, websocketService) {
        var _this = this;
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
        this.websocketService = websocketService;
        this.loadingModal = this.loadingCtrl.create({
            content: 'Please wait...'
        });
        this.refresh(null)
            .catch(function (e) {
            console.log(e);
        });
        events.subscribe('notification', function () {
            _this.settingsService.menu === 'notifications' && _this.choosePage();
        });
    }
    ListPage_1 = ListPage;
    ListPage.prototype.refresh = function (refresher) {
        var _this = this;
        this.subitems = {};
        this.loading = true;
        this.loadingBalance = true;
        // If we navigated to this page, we will have an item available as a nav param
        return this.storage.get('blockchainAddress')
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
            .then(function (identity) {
            _this.websocketService.joinGroup(identity);
            return _this.choosePage();
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
                    graphArray = _this.graphService.graph.friends.filter(function (item) { return !!item.relationship[_this.settingsService.collections.CONTACT]; });
                    graphArray = _this.getDistinctFriends(graphArray).friend_list;
                    _this.graphService.sortTxnsByUsername(graphArray, false, _this.settingsService.collections.CONTACT);
                    _this.makeList(graphArray, 'Contacts', null);
                    _this.loading = false;
                }
                else if (_this.pageTitle == 'Groups') {
                    _this.subitems = {};
                    for (var i = 0; i < _this.graphService.graph.groups.length; i++) {
                        var item = _this.graphService.graph.groups[i];
                        var parentIdentity = _this.graphService.getParentIdentityFromTxn(item, _this.settingsService.collections.GROUP);
                        var itemIdentity = _this.graphService.getIdentityFromTxn(item, _this.settingsService.collections.GROUP);
                        if (parentIdentity) {
                            _this.subitems[parentIdentity.username_signature] = _this.subitems[parentIdentity.username_signature] || [];
                            _this.subitems[parentIdentity.username_signature].push({
                                pageTitle: _this.pageTitle,
                                identity: itemIdentity,
                                item: item
                            });
                        }
                        else {
                            graphArray.push(item);
                        }
                    }
                    _this.graphService.sortTxnsByUsername(graphArray, false, _this.settingsService.collections.GROUP);
                    _this.makeList(graphArray, 'Groups', null);
                    _this.loading = false;
                }
                else if (_this.pageTitle == 'Markets') {
                    _this.loading = false;
                    _this.graphService.sortTxnsByUsername(_this.graphService.graph.markets);
                    var marketList = _this.graphService.graph.markets.filter(function (item) {
                        var parentIdentity = _this.graphService.getParentIdentityFromTxn(item, _this.settingsService.collections.MARKET);
                        if (parentIdentity) {
                            _this.subitems[parentIdentity.username_signature] = _this.subitems[parentIdentity.username_signature] || [];
                            var identity = _this.graphService.getIdentityFromTxn(item, _this.settingsService.collections.MARKET);
                            _this.subitems[parentIdentity.username_signature].push({
                                title: 'Markets',
                                label: identity.username,
                                component: __WEBPACK_IMPORTED_MODULE_16__markets_market__["a" /* MarketPage */],
                                count: false,
                                color: '',
                                kwargs: {
                                    item: item,
                                    identity: identity,
                                    subitems: _this.subitems
                                },
                                root: true
                            });
                        }
                        return !parentIdentity;
                    });
                    return _this.makeList(marketList, '', { title: 'Markets', component: __WEBPACK_IMPORTED_MODULE_16__markets_market__["a" /* MarketPage */] })
                        .then(function (pages) {
                        _this.events.publish('menu', pages);
                        _this.loading = false;
                    });
                }
                else if (_this.pageTitle == 'Messages') {
                    public_key = _this.bulletinSecretService.key.getPublicKeyBuffer().toString('hex');
                    return _this.graphService.getNewMessages()
                        .then(function (graphArray) {
                        var messages = _this.markNew(public_key, graphArray, _this.graphService.new_messages_counts);
                        var friendsWithMessagesList = _this.getDistinctFriends(messages);
                        _this.populateRemainingFriends(friendsWithMessagesList.friend_list, friendsWithMessagesList.used_rids);
                        _this.loading = false;
                        _this.graphService.sortTxnsByUsername(friendsWithMessagesList.friend_list, false, _this.settingsService.collections.CONTACT);
                        return _this.makeList(friendsWithMessagesList.friend_list, '', { title: 'Messages', component: __WEBPACK_IMPORTED_MODULE_9__chat_chat__["a" /* ChatPage */] })
                            .then(function (pages) {
                            _this.events.publish('menu', pages);
                        });
                    }).catch(function (err) {
                        console.log(err);
                    });
                }
                else if (_this.pageTitle == 'Notifications') {
                    public_key = _this.bulletinSecretService.key.getPublicKeyBuffer().toString('hex');
                    var notifications = _this.graphService.getNotifications();
                    _this.loading = false;
                    notifications['notifications'].sort(function (a, b) {
                        try {
                            if (parseInt(a.time) < parseInt(b.time))
                                return 1;
                            if (parseInt(a.time) > parseInt(b.time))
                                return -1;
                            return 0;
                        }
                        catch (err) {
                            return 0;
                        }
                    });
                    notifications['notifications'].map(function (item) {
                        if (item.relationship[_this.settingsService.collections.MAIL] ||
                            item.relationship[_this.settingsService.collections.GROUP_MAIL]) {
                            item.component = __WEBPACK_IMPORTED_MODULE_13__mail_mailitem__["a" /* MailItemPage */];
                            item.item = _this.graphService.prepareMailItem(item, 'Inbox');
                            var identity = _this.graphService.getIdentityFromMessageTransaction(item);
                            item.label = 'Mail from ' + identity.username;
                        }
                        else if (item.relationship[_this.settingsService.collections.CHAT] ||
                            item.relationship[_this.settingsService.collections.GROUP_CHAT]) {
                            item.component = __WEBPACK_IMPORTED_MODULE_9__chat_chat__["a" /* ChatPage */];
                            var identity = _this.graphService.getIdentityFromMessageTransaction(item);
                            item.identity = identity;
                            item.label = 'Chat from ' + identity.username;
                        }
                        else if (item.relationship[_this.settingsService.collections.CALENDAR] ||
                            item.relationship[_this.settingsService.collections.GROUP_CALENDAR]) {
                            item.component = __WEBPACK_IMPORTED_MODULE_15__calendar_calendar__["a" /* CalendarPage */];
                            var identity = _this.graphService.getIdentityFromMessageTransaction(item);
                            item.identity = identity;
                            item.label = 'Calendar entry from ' + identity.username;
                        }
                        else if (_this.graphService.graph.friend_requests.filter(function (fr) { return fr.rid === item.rid; }).length > 0) {
                            item.component = ListPage_1;
                            var identity = _this.graphService.getIdentityFromTxn(item);
                            item.identity = identity;
                            item.label = 'Contact request from ' + identity.username;
                            item.pageTitle = 'Contact Requests';
                            item.item = item;
                        }
                        else if (_this.graphService.graph.friends.filter(function (f) { return f.rid === item.rid; }).length > 0) {
                            item.component = __WEBPACK_IMPORTED_MODULE_10__profile_profile__["a" /* ProfilePage */];
                            var identity = _this.graphService.getIdentityFromMessageTransaction(item);
                            item.identity = identity;
                            item.label = 'Contact ' + identity.username + ' accepted your request ';
                            item.pageTitle = 'Contacts';
                            item.item = item;
                        }
                        else if (item.relationship.signature_request) {
                            item.component = __WEBPACK_IMPORTED_MODULE_11__signaturerequest_signaturerequest__["a" /* SignatureRequestPage */];
                        }
                    });
                    return _this.makeList(notifications['notifications'], '', { title: 'Notifications', component: __WEBPACK_IMPORTED_MODULE_9__chat_chat__["a" /* ChatPage */] })
                        .then(function (pages) {
                        pages.length > 0 && _this.events.publish('menu', pages);
                    });
                }
                else if (_this.pageTitle == 'Community') {
                    public_key = _this.bulletinSecretService.key.getPublicKeyBuffer().toString('hex');
                    _this.loading = false;
                    _this.graphService.sortTxnsByUsername(_this.graphService.graph.groups);
                    var groupList = _this.graphService.graph.groups.filter(function (item) {
                        var parentIdentity = _this.graphService.getParentIdentityFromTxn(item, _this.settingsService.collections.GROUP);
                        if (parentIdentity) {
                            _this.subitems[parentIdentity.username_signature] = _this.subitems[parentIdentity.username_signature] || [];
                            var identity = _this.graphService.getIdentityFromTxn(item, _this.settingsService.collections.GROUP);
                            _this.subitems[parentIdentity.username_signature].push({
                                title: 'Community',
                                label: identity.username,
                                component: __WEBPACK_IMPORTED_MODULE_9__chat_chat__["a" /* ChatPage */],
                                count: false,
                                color: '',
                                kwargs: {
                                    item: item,
                                    identity: identity,
                                    subitems: _this.subitems
                                },
                                root: true
                            });
                        }
                        return !parentIdentity;
                    });
                    return _this.makeList(groupList, '', { title: 'Community', component: __WEBPACK_IMPORTED_MODULE_9__chat_chat__["a" /* ChatPage */] })
                        .then(function (pages) {
                        _this.events.publish('menu', pages);
                        _this.loading = false;
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
                        _this.graphService.sortTxnsByUsername(friendsWithMessagesList.friend_list, false, _this.settingsService.collections.CONTACT);
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
                    });
                }
                else if (_this.pageTitle == 'Contact Requests') {
                    return _this.graphService.getFriendRequests()
                        .then(function () {
                        var graphArray = _this.graphService.graph.friend_requests;
                        _this.graphService.sortTxnsByUsername(graphArray, false, _this.settingsService.collections.CONTACT);
                        _this.loading = false;
                        return _this.makeList(graphArray, 'Contact Requests', null);
                    });
                }
                else if (_this.pageTitle == 'Sent Requests') {
                    return _this.graphService.getSentFriendRequests()
                        .then(function () {
                        var graphArray = _this.graphService.graph.sent_friend_requests;
                        _this.graphService.sortTxnsByUsername(graphArray, false, _this.settingsService.collections.CONTACT);
                        _this.loading = false;
                        return _this.makeList(graphArray, 'Sent Requests', null);
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
                    _this.friend_request = _this.navParams.get('item').item;
                    resolve();
                }
                else if (_this.pageTitle == 'Sign Ins') {
                    _this.rid = _this.navParams.get('item').transaction.rid;
                    _this.graphService.getSignIns(_this.rid)
                        .then(function (signIn) {
                        _this.signIn = signIn[0];
                        _this.signInText = _this.signIn.relationship.signIn;
                        resolve();
                    }).catch(function (e) {
                        console.log(e);
                        reject(e);
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
                var item = graphArray[i];
                var identity = item.identity || _this.graphService.getIdentityFromTxn(item);
                if (page) {
                    var component = item.component || page.component;
                    var label = identity && identity.username;
                    items.push({
                        title: page.title,
                        label: item.label || label,
                        component: component,
                        count: false,
                        color: '',
                        kwargs: {
                            item: item.item || item,
                            identity: identity,
                            subitems: _this.subitems
                        },
                        root: true
                    });
                }
                else {
                    _this.items.push({
                        pageTitle: pageTitle,
                        identity: identity,
                        item: item
                    });
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
            this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_9__chat_chat__["a" /* ChatPage */], item);
        }
        else if (this.pageTitle == 'Community') {
            this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_9__chat_chat__["a" /* ChatPage */], item);
        }
        else if (this.pageTitle == 'Markets') {
            this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_16__markets_market__["a" /* MarketPage */], item);
        }
        else if (this.pageTitle == 'Groups') {
            this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_10__profile_profile__["a" /* ProfilePage */], item);
        }
        else if (this.pageTitle == 'Contacts') {
            this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_10__profile_profile__["a" /* ProfilePage */], item);
        }
        else if (this.pageTitle == 'Notifications') {
            if (item.relationship[this.settingsService.collections.SIGNATURE_REQUEST]) {
                this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_11__signaturerequest_signaturerequest__["a" /* SignatureRequestPage */], item);
            }
            else if (item.relationship[this.settingsService.collections.MAIL]) {
                this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_13__mail_mailitem__["a" /* MailItemPage */], item);
            }
        }
        else {
            this.navCtrl.push(ListPage_1, {
                item: item
            });
        }
    };
    ListPage.prototype.accept = function () {
        var _this = this;
        this.loading = true;
        var rids = this.graphService.generateRids(this.friend_request.relationship[this.settingsService.collections.CONTACT]);
        return this.graphService.addFriend(this.friend_request.relationship[this.settingsService.collections.CONTACT], rids.rid, rids.requested_rid, this.friend_request.requested_rid).then(function (txn) {
            return _this.graphService.refreshFriendsAndGroups();
        })
            .then(function () {
            _this.loading = false;
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
    ListPage.prototype.getIdentity = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            var buttons = [];
            buttons.push({
                text: 'Add',
                handler: function (data) {
                    resolve(data.identity);
                }
            });
            var alert = _this.alertCtrl.create({
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
        });
    };
    ListPage.prototype.addFriend = function () {
        var _this = this;
        return this.getPromo()
            .then(function (promo_code) {
            if (_this.settingsService.remoteSettings.restricted) {
                return _this.getIdentity()
                    .then(function (data) {
                    return _this.graphService.addFriendFromSkylink(data.identity);
                });
            }
            if (promo_code) {
                var promo_1;
                return _this.graphService.getPromotion(promo_code)
                    .then(function (promotion) {
                    promo_1 = promotion.relationship[_this.settingsService.collections.AFFILIATE].target;
                    _this.graphService.addFriend(promo_1, null, promotion.rid, promotion.requested_rid);
                })
                    .then(function () {
                    return _this.graphService.addFriend(promo_1); // add friend to global context
                });
            }
            else {
                return _this.getIdentity()
                    .then(function (identity) {
                    return _this.graphService.addFriend(JSON.parse(identity));
                });
            }
        })
            .then(function () {
            var alert = _this.alertCtrl.create();
            alert.setTitle('Contact added');
            alert.setSubTitle('Your contact was added successfully');
            alert.addButton('Ok');
            alert.present();
            return _this.choosePage();
        });
    };
    ListPage.prototype.addGroup = function () {
        var _this = this;
        var group;
        return this.getPromo()
            .then(function (promo_code) {
            if (_this.settingsService.remoteSettings.restricted) {
                return _this.getIdentity()
                    .then(function (data) {
                    return _this.graphService.addGroupFromSkylink(data.identity);
                });
            }
            if (promo_code) {
                return _this.graphService.getPromotion(promo_code)
                    .then(function (promotion) {
                    group = promotion.relationship[_this.settingsService.collections.AFFILIATE].target;
                    group.parent = _this.graphService.toIdentity(promotion.relationship[_this.settingsService.collections.AFFILIATE].contract);
                    return _this.graphService.addGroup(group, promotion.rid, null, promotion.requested_rid)
                        .then(function () {
                        return _this.graphService.addGroup(group); // add group to global context
                    });
                });
            }
            else {
                return _this.getIdentity()
                    .then(function (identity) {
                    group = identity;
                    return _this.graphService.addGroup(JSON.parse(identity));
                });
            }
        })
            .then(function () {
            _this.websocketService.joinGroup(group);
            var alert = _this.alertCtrl.create();
            alert.setTitle('Group added');
            alert.setSubTitle('Your group was added successfully');
            alert.addButton('Ok');
            alert.present();
            return _this.choosePage();
        });
    };
    ListPage.prototype.getPromo = function () {
        var _this = this;
        return new Promise(function (resolve, reject) {
            var alert = _this.alertCtrl.create({
                title: 'Do you have a promotion code?',
                subTitle: 'If so, enter it now, otherwise, leave blank.',
                inputs: [
                    {
                        name: 'promo',
                        placeholder: 'Promo code'
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
                        text: 'confirm',
                        handler: function (data) {
                            resolve(data.promo);
                        }
                    }
                ]
            });
            alert.present();
        });
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
            selector: 'page-list',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/list/list.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n    <ion-title *ngIf="loading">Loading...</ion-title>\n    <ion-title *ngIf="!loading">{{label}}</ion-title>\n  </ion-navbar>\n</ion-header>\n\n<ion-content>\n  <ion-refresher (ionRefresh)="refresh($event)">\n    <ion-refresher-content></ion-refresher-content>\n  </ion-refresher>\n  <ion-spinner *ngIf="loading"></ion-spinner>\n  <button *ngIf="pageTitle ==\'Contacts\'" ion-button secondary (click)="addFriend()">Add contact</button>\n  <button *ngIf="pageTitle ==\'Groups\'" ion-button secondary (click)="addGroup()">Add group</button>\n  <button *ngIf="pageTitle ==\'Groups\'" ion-button secondary (click)="createGroup()">Create group</button>\n  <ion-card *ngIf="items && items.length == 0">\n      <ion-card-content>\n        <ion-card-title style="text-overflow:ellipsis;" text-wrap>\n          No items to display.\n      </ion-card-title>\n    </ion-card-content>\n  </ion-card>\n  <ion-list>\n    <ng-container *ngFor="let item of items">\n      <button ion-item (click)="itemTapped($event, item)">\n        <span *ngIf="pageTitle ==\'Groups\'">{{item.identity.username}}</span>\n        <span *ngIf="pageTitle ==\'Contact Requests\'">{{item.identity.username}}</span>\n        <span *ngIf="pageTitle ==\'Messages\' && !identity.new && !identity.parent && identity.username">{{ identity.username}}</span>\n        <span *ngIf="pageTitle ==\'Messages\' && !identity.new && identity.parent"><ion-note>&nbsp;&nbsp;&nbsp;&nbsp;{{identity.username}}</ion-note></span>\n        <span *ngIf="pageTitle ==\'Community\' && !identity.new && !identity.parent && identity.username">{{ identity.username}}</span>\n        <span *ngIf="pageTitle ==\'Community\' && !identity.new && identity.parent"><ion-note>&nbsp;&nbsp;&nbsp;&nbsp;{{identity.username}}</ion-note></span>\n        <span *ngIf="pageTitle ==\'Chat\' && identity.new"><strong>{{item.identity.username}}</strong></span>\n        <span *ngIf="pageTitle ==\'Contacts\'">{{item.identity.username}}</span>\n      </button>\n      <ng-container *ngIf="subitems[item.identity.username_signature]">\n        <button ion-item (click)="itemTapped($event, subitem)" *ngFor="let subitem of subitems[item.identity.username_signature]">\n          <span><ion-note>&nbsp;&nbsp;&nbsp;&nbsp;{{subitem.identity.username}}</ion-note></span>\n        </button>\n      </ng-container>\n    </ng-container>\n  </ion-list>\n  <div *ngIf="selectedItem && pageTitle ==\'Sent Requests\'" padding>\n  </div>\n  <div *ngIf="selectedItem && pageTitle ==\'Contact Requests\'" padding>\n\n    <ion-card *ngIf="friend_request">\n      <ion-card-header>\n        <p><strong>New contact request from {{friend_request.username}}</strong> </p>\n      </ion-card-header>\n      <ion-card-content>\n        <p>{{friend_request.username}} would like to be added as a contact</p>\n        <button ion-button secondary (click)="accept()">Accept</button>\n      </ion-card-content>\n    </ion-card>\n    <!-- for now, we can\'t do p2p on WKWebView\n    <button *ngIf="pageTitle == \'Contact Requests\'" ion-button secondary (click)="accept(selectedItem.transaction)">Accept Request</button>\n\n    <button *ngIf="pageTitle == \'Contact Requests\'" ion-button secondary (click)="send_receipt(selectedItem.transaction)">Send Receipt</button>\n    -->\n  </div>\n  <div *ngIf="selectedItem && pageTitle ==\'Contacts\'" padding>\n    You navigated here from <b>{{selectedItem.transaction.rid}}</b>\n  </div>\n  <div *ngIf="selectedItem && pageTitle ==\'Posts\'" padding>\n    <a href="{{selectedItem.transaction.relationship.postText}}" target="_blank">{{selectedItem.transaction.relationship.postText}}</a>\n  </div>\n  <div *ngIf="selectedItem && pageTitle ==\'Sign Ins\'" padding>\n\n    <ion-card>\n      <ion-card-header>\n        <p><strong>{{selectedItem.transaction.identity.username}}</strong> has sent you an authorization offer. Accept offer with the \'Sign in\' button.</p>\n      </ion-card-header>\n      <ion-card-content>\n        <button ion-button secondary (click)="sendSignIn()">Sign in</button>\n        Sign in code: {{signInText}}\n      </ion-card-content>\n    </ion-card>\n    <!-- for now, we can\'t do p2p on WKWebView\n    <button *ngIf="pageTitle == \'Contact Requests\'" ion-button secondary (click)="accept(selectedItem.transaction)">Accept Request</button>\n\n    <button *ngIf="pageTitle == \'Contact Requests\'" ion-button secondary (click)="send_receipt(selectedItem.transaction)">Send Receipt</button>\n    -->\n  </div>\n</ion-content>\n'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/list/list.html"*/
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
            __WEBPACK_IMPORTED_MODULE_7__app_settings_service__["a" /* SettingsService */],
            __WEBPACK_IMPORTED_MODULE_1_ionic_angular__["l" /* ToastController */],
            __WEBPACK_IMPORTED_MODULE_14__app_websocket_service__["a" /* WebSocketService */]])
    ], ListPage);
    return ListPage;
}());

//# sourceMappingURL=list.js.map

/***/ }),

/***/ 70:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return ProfilePage; });
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_0__angular_core__ = __webpack_require__(0);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_1_ionic_angular__ = __webpack_require__(5);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_2__ionic_storage__ = __webpack_require__(48);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_3__app_graph_service__ = __webpack_require__(16);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_4__app_bulletinSecret_service__ = __webpack_require__(14);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_5__app_wallet_service__ = __webpack_require__(25);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_6__app_transaction_service__ = __webpack_require__(20);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_7__list_list__ = __webpack_require__(69);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_8__chat_chat__ = __webpack_require__(227);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_9__angular_http__ = __webpack_require__(18);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_10__app_settings_service__ = __webpack_require__(10);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_11__mail_compose__ = __webpack_require__(109);
/* harmony import */ var __WEBPACK_IMPORTED_MODULE_12__sendreceive_sendreceive__ = __webpack_require__(228);
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
        this.item = this.navParams.get('item');
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
        this.isMe = this.graphService.isMe(this.identity);
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
            identity: subGroup.relationship[this.settingsService.collections.GROUP],
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
    ProfilePage.prototype.sendCoins = function () {
        this.navCtrl.push(__WEBPACK_IMPORTED_MODULE_12__sendreceive_sendreceive__["a" /* SendReceive */], {
            identity: this.identity
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
            selector: 'page-profile',template:/*ion-inline-start:"/home/mvogel/yadacoinmobile/src/pages/profile/profile.html"*/'<ion-header>\n  <ion-navbar>\n    <button ion-button menuToggle color="{{color}}">\n      <ion-icon name="menu"></ion-icon>\n    </button>\n  </ion-navbar>\n</ion-header>\n<ion-content padding>\n  <ion-row>\n    <ion-col text-center>\n      <ion-item>\n        <h1>{{identity.username}}</h1></ion-item>\n    </ion-col>\n    <ion-col>\n      <button ion-button large secondary (click)="addFriend()" *ngIf="isAdded === false && group !== true && isMe === false">\n        Add contact&nbsp;<ion-icon name="create"></ion-icon>\n      </button>\n      <button ion-button large secondary (click)="createSubGroup()" *ngIf="isAdded === true && group === true && !identity.parent && identity.public_key === bulletinSecretService.identity.public_key">\n        Create sub-group&nbsp;<ion-icon name="create"></ion-icon>\n      </button>\n      <button ion-button large secondary (click)="compose()" *ngIf="isAdded === true">\n        Compose message&nbsp;<ion-icon name="create"></ion-icon>\n      </button>\n      <button ion-button large secondary (click)="message()" *ngIf="isAdded === true && !group">\n        Chat&nbsp;<ion-icon name="create"></ion-icon>\n      </button>\n      <button ion-button large secondary (click)="message()" *ngIf="isAdded === true && group === true">\n        Group chat&nbsp;<ion-icon name="create"></ion-icon>\n      </button>\n      <button ion-button large secondary (click)="sendCoins()" *ngIf="!group && isMe === false && !settingsService.remoteSettings.restricted">\n        Send Coins&nbsp;<ion-icon name="cash"></ion-icon>\n      </button>\n      <a href="https://centeridentity.com/sia-download?skylink={{identity.skylink}}" *ngIf="identity.skylink" target="_blank">\n        <button ion-button large secondary>\n          Download&nbsp;<ion-icon name="create"></ion-icon>\n        </button>\n      </a>\n    </ion-col>\n  </ion-row>\n  <h4>Manage access</h4>\n  <ion-row>\n    <ion-list>\n      <ion-item>\n\n      </ion-item>\n    </ion-list>\n  </ion-row>\n  <ion-row *ngIf="settingsService.remoteSettings.restricted">\n    <h4>Public identity <ion-spinner *ngIf="busy"></ion-spinner></h4>\n    <ion-item>\n      <ion-textarea type="text" [(ngModel)]="identitySkylink" autoGrow="true" rows="1"></ion-textarea>\n    </ion-item>\n  </ion-row>\n  <ion-row *ngIf="!settingsService.remoteSettings.restricted">\n    <h4>Public identity</h4>\n    <ion-item>\n      <ion-textarea type="text" [value]="identityJson" autoGrow="true" rows="5"></ion-textarea>\n    </ion-item>\n  </ion-row>\n  <h4 *ngIf="identity.collection === settingsService.collections.GROUP">Sub groups</h4>\n  <ion-row>\n    <ion-list>\n      <ng-container *ngFor="let group of graphService.graph.groups">\n        <ion-item *ngIf="group.relationship[settingsService.collections.GROUP].parent && group.relationship[settingsService.collections.GROUP].parent.username_signature === identity.username_signature" (click)="openSubGroup(group)">\n            {{group.relationship[settingsService.collections.GROUP].username}}\n        </ion-item>\n      </ng-container>\n    </ion-list>\n  </ion-row>\n</ion-content>'/*ion-inline-end:"/home/mvogel/yadacoinmobile/src/pages/profile/profile.html"*/
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

/***/ })

},[424]);
//# sourceMappingURL=main.js.map