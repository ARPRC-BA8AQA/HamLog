from flask import jsonify

def ok(data=None, msg="ok", http_status=200):
    return jsonify({"code": 200, "msg": msg, "data": data}), http_status

def fail(code, msg, data=None):
    return jsonify({"code": code, "msg": msg, "data": data}), code
