(window["webpackJsonp"] = window["webpackJsonp"] || []).push([["main"],{

/***/ "./src/$$_lazy_route_resource lazy recursive":
/*!**********************************************************!*\
  !*** ./src/$$_lazy_route_resource lazy namespace object ***!
  \**********************************************************/
/*! no static exports found */
/***/ (function(module, exports) {

function webpackEmptyAsyncContext(req) {
	// Here Promise.resolve().then() is used instead of new Promise() to prevent
	// uncaught exception popping up in devtools
	return Promise.resolve().then(function() {
		var e = new Error("Cannot find module '" + req + "'");
		e.code = 'MODULE_NOT_FOUND';
		throw e;
	});
}
webpackEmptyAsyncContext.keys = function() { return []; };
webpackEmptyAsyncContext.resolve = webpackEmptyAsyncContext;
module.exports = webpackEmptyAsyncContext;
webpackEmptyAsyncContext.id = "./src/$$_lazy_route_resource lazy recursive";

/***/ }),

/***/ "./src/app/app.component.css":
/*!***********************************!*\
  !*** ./src/app/app.component.css ***!
  \***********************************/
/*! no static exports found */
/***/ (function(module, exports) {

module.exports = ""

/***/ }),

/***/ "./src/app/app.component.html":
/*!************************************!*\
  !*** ./src/app/app.component.html ***!
  \************************************/
/*! no static exports found */
/***/ (function(module, exports) {

module.exports = "<!--The content below is only a placeholder and can be replaced.-->\n<div style=\"text-align:center\">\n  <h1>\n    Yada Coin Explorer\n  </h1>\n</div>\n<app-search-form></app-search-form>\n\n"

/***/ }),

/***/ "./src/app/app.component.ts":
/*!**********************************!*\
  !*** ./src/app/app.component.ts ***!
  \**********************************/
/*! exports provided: AppComponent */
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
__webpack_require__.r(__webpack_exports__);
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "AppComponent", function() { return AppComponent; });
/* harmony import */ var _angular_core__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! @angular/core */ "./node_modules/@angular/core/fesm5/core.js");
var __decorate = (undefined && undefined.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};

var AppComponent = /** @class */ (function () {
    function AppComponent() {
        this.title = 'explorer';
    }
    AppComponent = __decorate([
        Object(_angular_core__WEBPACK_IMPORTED_MODULE_0__["Component"])({
            selector: 'app-root',
            template: __webpack_require__(/*! ./app.component.html */ "./src/app/app.component.html"),
            styles: [__webpack_require__(/*! ./app.component.css */ "./src/app/app.component.css")]
        })
    ], AppComponent);
    return AppComponent;
}());



/***/ }),

/***/ "./src/app/app.module.ts":
/*!*******************************!*\
  !*** ./src/app/app.module.ts ***!
  \*******************************/
/*! exports provided: AppModule */
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
__webpack_require__.r(__webpack_exports__);
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "AppModule", function() { return AppModule; });
/* harmony import */ var _angular_platform_browser__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! @angular/platform-browser */ "./node_modules/@angular/platform-browser/fesm5/platform-browser.js");
/* harmony import */ var _angular_forms__WEBPACK_IMPORTED_MODULE_1__ = __webpack_require__(/*! @angular/forms */ "./node_modules/@angular/forms/fesm5/forms.js");
/* harmony import */ var _angular_core__WEBPACK_IMPORTED_MODULE_2__ = __webpack_require__(/*! @angular/core */ "./node_modules/@angular/core/fesm5/core.js");
/* harmony import */ var _angular_http__WEBPACK_IMPORTED_MODULE_3__ = __webpack_require__(/*! @angular/http */ "./node_modules/@angular/http/fesm5/http.js");
/* harmony import */ var _app_component__WEBPACK_IMPORTED_MODULE_4__ = __webpack_require__(/*! ./app.component */ "./src/app/app.component.ts");
/* harmony import */ var _search_form_search_form_component__WEBPACK_IMPORTED_MODULE_5__ = __webpack_require__(/*! ./search-form/search-form.component */ "./src/app/search-form/search-form.component.ts");
var __decorate = (undefined && undefined.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};






var AppModule = /** @class */ (function () {
    function AppModule() {
    }
    AppModule = __decorate([
        Object(_angular_core__WEBPACK_IMPORTED_MODULE_2__["NgModule"])({
            declarations: [
                _app_component__WEBPACK_IMPORTED_MODULE_4__["AppComponent"],
                _search_form_search_form_component__WEBPACK_IMPORTED_MODULE_5__["SearchFormComponent"]
            ],
            imports: [
                _angular_platform_browser__WEBPACK_IMPORTED_MODULE_0__["BrowserModule"],
                _angular_forms__WEBPACK_IMPORTED_MODULE_1__["FormsModule"],
                _angular_http__WEBPACK_IMPORTED_MODULE_3__["HttpModule"]
            ],
            providers: [],
            bootstrap: [_app_component__WEBPACK_IMPORTED_MODULE_4__["AppComponent"]]
        })
    ], AppModule);
    return AppModule;
}());



/***/ }),

/***/ "./src/app/search-form/search-form.component.css":
/*!*******************************************************!*\
  !*** ./src/app/search-form/search-form.component.css ***!
  \*******************************************************/
/*! no static exports found */
/***/ (function(module, exports) {

module.exports = ""

/***/ }),

/***/ "./src/app/search-form/search-form.component.html":
/*!********************************************************!*\
  !*** ./src/app/search-form/search-form.component.html ***!
  \********************************************************/
/*! no static exports found */
/***/ (function(module, exports) {

module.exports = "<h2>Current block height: {{current_height}}</h2>\n<h2>Coins in circulation: {{circulating}}</h2>\n<h3>Maximum supply: 21,000,000</h3>\n<h3>Network hash rate: {{hashrate}}h/s</h3>\n<h3>Difficulty: {{difficulty}}</h3>\n<h3>Hashing algorithm: RandomX Variant (rx/yada)</h3>\n<form (ngSubmit)=\"onSubmit()\" #searchForm=\"ngForm\">\n    <input class=\"form-control\" [(ngModel)]=\"model.term\" name=\"term\" placeholder=\"Wallet address, Txn Id, Block height...\">\n    <button style=\"margin-top: 15px\" class=\"btn btn-success\">Search</button>\n</form>\n<div *ngIf=\"searching\"><strong>Searching...</strong></div>\n<div *ngIf=\"(!searching && submitted) && result.length === 0\"><strong>No results</strong></div>\n<h2 *ngIf=\"resultType === 'txn_outputs_to'\">Balance: {{balance}}</h2>\n<ul *ngIf=\"resultType.substr(0, 6) === 'failed'\">\n    <li *ngFor=\"let transaction of result\">\n        <h3>Failed transactions</h3>\n        <p><strong>exception class: </strong>{{transaction.reason}}</p>\n        <p><strong>traceback: </strong><textarea class=\"form-control\" rows=\"10\">{{transaction.error}}</textarea></p>\n        <p><strong>public_key: </strong><a href=\"/explorer?term={{transaction.public_key}}\">{{transaction.public_key}}</a></p>\n        <p><strong>signature: </strong><a href=\"/explorer?term={{transaction.id}}\">{{transaction.id}}</a></p>\n        <p><strong>hash: </strong>{{transaction.hash}}</p>\n        <p><strong>fee: </strong>{{transaction.fee}}</p>\n        <p><strong>diffie-hellman public key: </strong>{{transaction.dh_public_key}}</p>\n        <p><strong>relationship identifier: </strong><a href=\"/explorer?term={{transaction.rid}}\">{{transaction.rid}}</a></p>\n        <p><strong>relationship data: </strong><textarea class=\"form-control\">{{transaction.relationship}}</textarea></p>\n        <div *ngIf=\"transaction.inputs.length === 0\"><strong>No inputs</strong></div>\n        <div *ngIf=\"transaction.inputs.length > 0\">\n            <h3>Inputs</h3>\n            <ul>\n                <li *ngFor=\"let input of transaction.inputs\"><strong>Signature: </strong><a href=\"/explorer?term={{input.id}}\">{{input.id}}</a></li>\n            </ul>\n        </div>\n        <div *ngIf=\"transaction.outputs.length === 0\"><strong>No outputs</strong></div>\n        <div *ngIf=\"transaction.outputs.length > 0\">\n            <h3>Outputs</h3>\n            <ul *ngFor=\"let output of transaction.outputs\">\n                <li><strong>Address: </strong><a href=\"/explorer?term={{output.to}}\">{{output.to}}</a></li>\n                <li><strong>Amount: </strong>{{output.value}}</li>\n                <hr>\n            </ul>\n        </div>\n    </li>\n</ul>\n<ul *ngIf=\"resultType.substr(0, 7) === 'mempool'\">\n    <li *ngFor=\"let transaction of result\">\n        <h3>Mempool</h3>\n        <p><strong>public_key: </strong><a href=\"/explorer?term={{transaction.public_key}}\">{{transaction.public_key}}</a></p>\n        <p><strong>signature: </strong><a href=\"/explorer?term={{transaction.id}}\">{{transaction.id}}</a></p>\n        <p><strong>hash: </strong>{{transaction.hash}}</p>\n        <p><strong>fee: </strong>{{transaction.fee}}</p>\n        <p><strong>diffie-hellman public key: </strong>{{transaction.dh_public_key}}</p>\n        <p><strong>relationship identifier: </strong><a href=\"/explorer?term={{transaction.rid}}\">{{transaction.rid}}</a></p>\n        <p><strong>relationship data: </strong><textarea class=\"form-control\">{{transaction.relationship}}</textarea></p>\n        <div *ngIf=\"transaction.inputs.length === 0\"><strong>No inputs</strong></div>\n        <div *ngIf=\"transaction.inputs.length > 0\">\n            <h3>Inputs</h3>\n            <ul>\n                <li *ngFor=\"let input of transaction.inputs\"><strong>Signature: </strong><a href=\"/explorer?term={{input.id}}\">{{input.id}}</a></li>\n            </ul>\n        </div>\n        <div *ngIf=\"transaction.outputs.length === 0\"><strong>No outputs</strong></div>\n        <div *ngIf=\"transaction.outputs.length > 0\">\n            <h3>Outputs</h3>\n            <ul *ngFor=\"let output of transaction.outputs\">\n                <li><strong>Address: </strong><a href=\"/explorer?term={{output.to}}\">{{output.to}}</a></li>\n                <li><strong>Amount: </strong>{{output.value}}</li>\n                <hr>\n            </ul>\n        </div>\n    </li>\n</ul>\n<ul *ngIf=\"resultType.substr(0, 5) === 'block' || resultType.substr(0, 3) === 'txn'\">\n    <li *ngFor=\"let block of result\">\n        <a href=\"/explorer?term={{block.index}}\"><h3>Block {{block.index}}</h3></a>\n        <p><strong>version: </strong>{{block.version}}</p>\n        <p><strong>target: </strong>{{block.target}}</p>\n        <p><strong>nonce: </strong>{{block.nonce}}</p>\n        <p><strong>merkleRoot: </strong>{{block.merkleRoot}}</p>\n        <p><strong>index: </strong>{{block.index}}</p>\n        <p><strong>special min: </strong>{{block.special_min}}</p>\n        <p><strong>time: </strong>{{block.time}}</p>\n        <p><strong>previous hash: </strong><a href=\"/explorer?term={{block.prevHash}}\">{{block.prevHash}}</a></p>\n        <p><strong>public_key: </strong><a href=\"/explorer?term={{block.public_key}}\">{{block.public_key}}</a></p>\n        <p><strong>signature: </strong><a href=\"/explorer?term={{block.id}}\">{{block.id}}</a></p>\n        <p><strong>hash: </strong><a href=\"/explorer?term={{block.hash}}\">{{block.hash}}</a></p>\n        <h3>Transactions</h3>\n        <ul>\n            <li *ngFor=\"let transaction of block.transactions\">\n                <p><strong>public_key: </strong><a href=\"/explorer?term={{transaction.public_key}}\">{{transaction.public_key}}</a></p>\n                <p><strong>signature: </strong>{{transaction.id}}</p>\n                <p><strong>hash: </strong>{{transaction.hash}}</p>\n                <p><strong>fee: </strong>{{transaction.fee}}</p>\n                <p><strong>diffie-hellman public key: </strong>{{transaction.dh_public_key}}</p>\n                <p><strong>relationship identifier: </strong><a href=\"/explorer?term={{transaction.rid}}\">{{transaction.rid}}</a></p>\n                <p><strong>relationship data: </strong><textarea class=\"form-control\">{{transaction.relationship}}</textarea></p>\n                <div *ngIf=\"transaction.inputs.length === 0\"><strong>No inputs</strong></div>\n                <div *ngIf=\"transaction.inputs.length > 0\">\n                    <h3>Inputs</h3>\n                    <ul>\n                        <li *ngFor=\"let input of transaction.inputs\"><strong>Signature: </strong><a href=\"/explorer?term={{input.id}}\">{{input.id}}</a></li>\n                    </ul>\n                </div>\n                <div *ngIf=\"transaction.outputs.length === 0\"><strong>No outputs</strong></div>\n                <div *ngIf=\"transaction.outputs.length > 0\">\n                    <h3>Outputs</h3>\n                    <ul *ngFor=\"let output of transaction.outputs\">\n                        <li><strong>Address: </strong><a href=\"/explorer?term={{output.to}}\">{{output.to}}</a></li>\n                        <li><strong>Amount: </strong>{{output.value}}</li>\n                        <hr>\n                    </ul>\n                </div>\n            </li>\n        </ul>\n    </li>\n</ul>"

/***/ }),

/***/ "./src/app/search-form/search-form.component.ts":
/*!******************************************************!*\
  !*** ./src/app/search-form/search-form.component.ts ***!
  \******************************************************/
/*! exports provided: SearchFormComponent */
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
__webpack_require__.r(__webpack_exports__);
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "SearchFormComponent", function() { return SearchFormComponent; });
/* harmony import */ var _angular_core__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! @angular/core */ "./node_modules/@angular/core/fesm5/core.js");
/* harmony import */ var _angular_http__WEBPACK_IMPORTED_MODULE_1__ = __webpack_require__(/*! @angular/http */ "./node_modules/@angular/http/fesm5/http.js");
/* harmony import */ var _search__WEBPACK_IMPORTED_MODULE_2__ = __webpack_require__(/*! ../search */ "./src/app/search.ts");
var __decorate = (undefined && undefined.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (undefined && undefined.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};



var SearchFormComponent = /** @class */ (function () {
    function SearchFormComponent(http) {
        var _this = this;
        this.http = http;
        this.model = new _search__WEBPACK_IMPORTED_MODULE_2__["Search"]('');
        this.result = [];
        this.resultType = '';
        this.balance = 0;
        this.searching = false;
        this.submitted = false;
        this.current_height = '';
        this.circulating = '';
        this.hashrate = '';
        this.difficulty = '';
        this.http.get('/api-stats')
            .subscribe(function (res) {
            _this.difficulty = _this.numberWithCommas(res.json()['stats']['difficulty']);
            _this.hashrate = _this.numberWithCommas(res.json()['stats']['network_hash_rate']);
            _this.current_height = _this.numberWithCommas(res.json()['stats']['height']);
            _this.circulating = _this.numberWithCommas(res.json()['stats']['circulating']);
            if (!window.location.search) {
                _this.http.get('/explorer-search?term=' + _this.current_height.replace(',', ''))
                    .subscribe(function (res) {
                    _this.result = res.json().result || [];
                    _this.resultType = res.json().resultType;
                    _this.balance = res.json().balance;
                    _this.searching = false;
                }, function (err) {
                    alert('something went terribly wrong!');
                });
            }
        }, function (err) {
            alert('something went terribly wrong!');
        });
        if (window.location.search) {
            this.searching = true;
            this.submitted = true;
            this.http.get('/explorer-search' + window.location.search)
                .subscribe(function (res) {
                _this.result = res.json().result || [];
                _this.resultType = res.json().resultType;
                _this.balance = res.json().balance;
                _this.searching = false;
            }, function (err) {
                alert('something went terribly wrong!');
            });
        }
    }
    SearchFormComponent.prototype.ngOnInit = function () {
    };
    SearchFormComponent.prototype.onSubmit = function () {
        var _this = this;
        this.searching = true;
        this.submitted = true;
        this.http.get('/explorer-search?term=' + encodeURIComponent(this.model.term))
            .subscribe(function (res) {
            _this.result = res.json().result || [];
            _this.resultType = res.json().resultType;
            _this.balance = res.json().balance;
            _this.searching = false;
        }, function (err) {
            alert('something went terribly wrong!');
        });
    };
    SearchFormComponent.prototype.numberWithCommas = function (x) {
        return x.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    };
    Object.defineProperty(SearchFormComponent.prototype, "diagnostic", {
        // TODO: Remove this when we're done
        get: function () { return JSON.stringify(this.model); },
        enumerable: true,
        configurable: true
    });
    SearchFormComponent = __decorate([
        Object(_angular_core__WEBPACK_IMPORTED_MODULE_0__["Component"])({
            selector: 'app-search-form',
            template: __webpack_require__(/*! ./search-form.component.html */ "./src/app/search-form/search-form.component.html"),
            styles: [__webpack_require__(/*! ./search-form.component.css */ "./src/app/search-form/search-form.component.css")]
        }),
        __metadata("design:paramtypes", [_angular_http__WEBPACK_IMPORTED_MODULE_1__["Http"]])
    ], SearchFormComponent);
    return SearchFormComponent;
}());



/***/ }),

/***/ "./src/app/search.ts":
/*!***************************!*\
  !*** ./src/app/search.ts ***!
  \***************************/
/*! exports provided: Search */
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
__webpack_require__.r(__webpack_exports__);
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "Search", function() { return Search; });
var Search = /** @class */ (function () {
    function Search(term) {
        this.term = term;
    }
    return Search;
}());



/***/ }),

/***/ "./src/environments/environment.ts":
/*!*****************************************!*\
  !*** ./src/environments/environment.ts ***!
  \*****************************************/
/*! exports provided: environment */
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
__webpack_require__.r(__webpack_exports__);
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "environment", function() { return environment; });
// This file can be replaced during build by using the `fileReplacements` array.
// `ng build ---prod` replaces `environment.ts` with `environment.prod.ts`.
// The list of file replacements can be found in `angular.json`.
var environment = {
    production: false
};
/*
 * In development mode, to ignore zone related error stack frames such as
 * `zone.run`, `zoneDelegate.invokeTask` for easier debugging, you can
 * import the following file, but please comment it out in production mode
 * because it will have performance impact when throw error
 */
// import 'zone.js/dist/zone-error';  // Included with Angular CLI.


/***/ }),

/***/ "./src/main.ts":
/*!*********************!*\
  !*** ./src/main.ts ***!
  \*********************/
/*! no exports provided */
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
__webpack_require__.r(__webpack_exports__);
/* harmony import */ var _angular_core__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! @angular/core */ "./node_modules/@angular/core/fesm5/core.js");
/* harmony import */ var _angular_platform_browser_dynamic__WEBPACK_IMPORTED_MODULE_1__ = __webpack_require__(/*! @angular/platform-browser-dynamic */ "./node_modules/@angular/platform-browser-dynamic/fesm5/platform-browser-dynamic.js");
/* harmony import */ var _app_app_module__WEBPACK_IMPORTED_MODULE_2__ = __webpack_require__(/*! ./app/app.module */ "./src/app/app.module.ts");
/* harmony import */ var _environments_environment__WEBPACK_IMPORTED_MODULE_3__ = __webpack_require__(/*! ./environments/environment */ "./src/environments/environment.ts");




if (_environments_environment__WEBPACK_IMPORTED_MODULE_3__["environment"].production) {
    Object(_angular_core__WEBPACK_IMPORTED_MODULE_0__["enableProdMode"])();
}
Object(_angular_platform_browser_dynamic__WEBPACK_IMPORTED_MODULE_1__["platformBrowserDynamic"])().bootstrapModule(_app_app_module__WEBPACK_IMPORTED_MODULE_2__["AppModule"])
    .catch(function (err) { return console.log(err); });


/***/ }),

/***/ 0:
/*!***************************!*\
  !*** multi ./src/main.ts ***!
  \***************************/
/*! no static exports found */
/***/ (function(module, exports, __webpack_require__) {

module.exports = __webpack_require__(/*! /media/john/4tb/home/mvogel/yadacoin/plugins/explorer/src/main.ts */"./src/main.ts");


/***/ })

},[[0,"runtime","vendor"]]]);
//# sourceMappingURL=main.js.map