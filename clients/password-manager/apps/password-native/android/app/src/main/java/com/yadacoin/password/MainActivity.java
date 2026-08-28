package com.yadacoin.password;

import android.os.Bundle;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(CallerIdentityPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
