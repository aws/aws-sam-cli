package com.amazonaws.examples;

import com.amazonaws.services.lambda.runtime.Context;
import org.json.simple.JSONObject;

public class Handler {
    public JSONObject handleRequest(JSONObject input, Context context) {
        //handle input
        JSONObject obj = new JSONObject();
        obj.put("statusCode", 200);
        return obj;
    }
}
