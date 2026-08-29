package io.yadacoin.passwordrotation.demo;

import android.os.Bundle;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(OpenPasswordManagerPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
