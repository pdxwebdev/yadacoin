"use strict";
var node_worker_1 = require("./node-worker.cjs");
var fnName = function (f) {
    if (f.name)
        return f.name;
    var ts = f.toString();
    return ts.slice(0, 9) == 'function ' && ts.slice(9, ts.indexOf('(', 9));
};
var abvList = [
    Int8Array,
    Uint8Array,
    Uint8ClampedArray,
    Int16Array,
    Uint16Array,
    Int32Array,
    Float32Array,
    Float64Array
];
if (typeof BigInt64Array != 'undefined')
    abvList.push(BigInt64Array);
if (typeof BigUint64Array != 'undefined')
    abvList.push(BigUint64Array);
var getAllPropertyKeys = function (o) {
    var keys = Object.getOwnPropertyNames(o);
    if (Object.getOwnPropertySymbols) {
        keys = keys.concat(Object.getOwnPropertySymbols(o));
    }
    return keys;
};
// optional chaining
var chainWrap = function (name, expr, short) {
    return "(" + expr + "||(" + short + "={}))" + name;
};
var encoder = {
    undefined: function () { return 'void 0'; },
    bigint: function (v) { return v.toString() + 'n'; },
    symbol: function (v) {
        var key = Symbol.keyFor(v);
        return key
            ? "Symbol.for(" + encoder.string(key) + ")"
            : "Symbol(" + encoder.string(v.toString().slice(7, -1)) + ")";
    },
    string: function (v) { return JSON.stringify(v); },
    "function": function (v, reg, ab) {
        var st = v.toString();
        if (st.indexOf('[native code]', 12) != -1)
            st = fnName(v);
        else if (v.prototype) {
            var nm = fnName(v);
            if (nm) {
                if (nm in reg)
                    return "self[" + encoder.string(nm) + "]";
                reg[nm] = true;
            }
            if (st[0] != 'c') {
                // Not an ES6 class; must iterate across the properties
                // Ignore superclass properties, assume superclass is handled elsewhere
                st = '(function(){var v=' + st;
                for (var _i = 0, _a = getAllPropertyKeys(v.prototype); _i < _a.length; _i++) {
                    var t = _a[_i];
                    var val = v.prototype[t];
                    if (t != 'constructor') {
                        st += ";v[" + encoder[typeof t](t) + "]=" + encoder[typeof val](val, reg, ab);
                    }
                }
                st += ';return v})()';
            }
        }
        return st;
    },
    object: function (v, reg, ab) {
        if (v == null)
            return 'null';
        var proto = Object.getPrototypeOf(v);
        if (abvList.indexOf(proto.constructor) != -1) {
            ab.push(v.buffer);
            return v;
        }
        else if (node_worker_1["default"].t.indexOf(proto.constructor) != -1) {
            ab.push(v);
            return v;
        }
        var out = '';
        out += "(function(){";
        var classDecl = '';
        for (var i = 0, l = proto; l.constructor != Object; l = Object.getPrototypeOf(l), ++i) {
            var cls = l.constructor;
            var nm = fnName(cls) || '_cls' + i;
            if (nm in reg)
                continue;
            var enc = encoder["function"](cls, reg, ab);
            if (enc == nm) {
                break;
            }
            else {
                reg[nm] = true;
                classDecl = "self[" + encoder.string(nm) + "]=" + enc + ";" + classDecl;
            }
        }
        var keys = getAllPropertyKeys(v);
        if (proto.constructor == Array) {
            var arrStr = '';
            for (var i = 0; i < v.length; ++i) {
                if (i in v) {
                    var val = v[i];
                    arrStr += encoder[typeof val](val, reg, ab);
                }
                arrStr += ',';
            }
            keys = keys.filter(function (k) {
                return isNaN(+k) && k != 'length';
            });
            out += "var v=[" + arrStr.slice(0, -1) + "]";
        }
        else {
            out +=
                classDecl +
                    ("var v=Object.create(self[" + encoder.string(fnName(proto.constructor) || '_cls0') + "].prototype);");
        }
        for (var _i = 0, keys_1 = keys; _i < keys_1.length; _i++) {
            var t = keys_1[_i];
            var _a = Object.getOwnPropertyDescriptor(v, t), enumerable = _a.enumerable, configurable = _a.configurable, get = _a.get, set = _a.set, writable = _a.writable, value = _a.value;
            var desc = '{';
            if (typeof writable == 'boolean') {
                desc += "writable:" + writable + ",value:" + encoder[typeof value](value, reg, ab);
            }
            else {
                desc += "get:" + (get ? encoder["function"](get, reg, ab) : 'void 0') + "," + (set ? encoder["function"](set, reg, ab) : 'void 0');
            }
            desc += ",enumerable:" + enumerable + ",configurable:" + configurable + "}";
            out += "Object.defineProperty(v, " + encoder[typeof t](t) + ", " + desc + ");";
        }
        return out + 'return v})()';
    },
    boolean: function (v) { return v.toString(); },
    number: function (v) { return v.toString(); }
};
/**
 * Creates a context for a worker execution environment
 * @param depList The dependencies in the worker environment
 * @returns An environment that can be built to a Worker. Note the fourth
 * element of the tuple, the global element registry, is currently not useful.
 */
function createContext(depList) {
    var depListStr = depList.toString();
    var depNames = depListStr
        .slice(depListStr.indexOf('[') + 1, depListStr.lastIndexOf(']'))
        .replace(/\s/g, '')
        .split(',');
    var depValues = depList();
    var out = '';
    var reg = {};
    var dat = {};
    var ab = [];
    for (var i = 0; i < depValues.length; ++i) {
        var key = depNames[i], value = depValues[i];
        var parts = key
            .replace(/\\/, '')
            .match(/^(.*?)(?=(\.|\[|$))|\[(.*?)\]|(\.(.*?))(?=(\.|\[|$))/g);
        var v = encoder[typeof value](value, reg, ab);
        if (typeof v == 'string') {
            var pfx = 'self.' + parts[0];
            var chain = pfx;
            for (var i_1 = 1; i_1 < parts.length; ++i_1) {
                chain = chainWrap(parts[i_1], chain, pfx);
                pfx += parts[i_1];
            }
            out += chain + "=" + v + ";";
        }
        else {
            // TODO: overwrite instead of assign
            var obj = dat;
            for (var i_2 = 0; i_2 < parts.length - 1; ++i_2) {
                obj = obj[parts[i_2]] = {};
            }
            obj[parts[parts.length - 1]] = v;
        }
    }
    return [out, dat, ab, reg];
}
exports.createContext = createContext;
var findTransferables = function (vals) {
    return vals.reduce(function (a, v) {
        var proto = Object.getPrototypeOf(v);
        if (abvList.indexOf(proto.constructor) != -1) {
            a.push(v.buffer);
        }
        else if (node_worker_1["default"].t.indexOf(proto.constructor) != -1) {
            a.push(v);
        }
        return a;
    }, []);
};
/**
 * Converts a function with dependencies into a worker
 * @param fn The function to workerize
 * @param deps The dependencies to add. This should include sub-dependencies.
 *             For example, if you are workerizing a function that calls
 *             another function, put any dependencies of the other function
 *             here as well.
 * @returns A function that accepts parameters and, as the last argument, a
 *          callback to use when the worker returns.
 */
function workerize(fn, deps) {
    var _a = createContext(deps), str = _a[0], msg = _a[1], tfl = _a[2], reg = _a[3];
    var currentCb;
    var runCount = 0;
    var callCount = 0;
    var worker = node_worker_1["default"](str + ";onmessage=function(e){for(var k in e.data){self[k]=e.data[k]}var h=" + encoder["function"](fn, reg, tfl) + ";var _p=function(d){d?typeof d.then=='function'?d.then(_p):postMessage(d,d.__transferList):postMessage(d)};onmessage=function(e){_p(h.apply(self,e.data))}}", msg, tfl, function (err, res) {
        ++runCount;
        currentCb(err, res);
    });
    var closed = false;
    var wfn = function () {
        var args = [];
        for (var _i = 0; _i < arguments.length; _i++) {
            args[_i] = arguments[_i];
        }
        var cb = args.pop();
        if (typeof cb != 'function')
            throw new TypeError('no callback provided');
        if (closed) {
            cb(new Error('worker thread closed'), null);
            return;
        }
        var lastCb = currentCb;
        var startCount = ++callCount;
        currentCb = function (err, r) {
            if (runCount == startCount)
                cb(err, r);
            else
                lastCb(err, r);
        };
        worker.postMessage(args, findTransferables(args));
    };
    wfn.close = function () {
        worker.terminate();
        closed = true;
    };
    return wfn;
}
exports.workerize = workerize;
