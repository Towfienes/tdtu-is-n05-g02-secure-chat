package vn.tdtu.securechat;

import android.content.Context;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.AtomicFile;
import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
import org.json.JSONArray;
import org.json.JSONException;

final class MessageCache {
    private static final String ALIAS = "chat-cache-v1";
    private static final int IV_BYTES = 12;
    private static final int TAG_BYTES = 16;
    private final AtomicFile storage;

    MessageCache(Context context) {
        storage = new AtomicFile(new File(context.getNoBackupFilesDir(), "messages.gcm"));
    }

    File file() {
        return storage.getBaseFile();
    }

    private static synchronized SecretKey key() throws GeneralSecurityException, IOException {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        if (store.getKey(ALIAS, null) instanceof SecretKey existing) return existing;
        KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setKeySize(256)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .build());
        return generator.generateKey();
    }

    void save(JSONArray messages) throws GeneralSecurityException, IOException {
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, key());
        byte[] iv = cipher.getIV();
        if (iv.length != IV_BYTES) throw new GeneralSecurityException("Unexpected GCM IV length");
        byte[] sealed = cipher.doFinal(messages.toString().getBytes(StandardCharsets.UTF_8));
        FileOutputStream output = storage.startWrite();
        try {
            output.write(iv);
            output.write(sealed);
            storage.finishWrite(output);
        } catch (IOException error) {
            storage.failWrite(output);
            throw error;
        }
    }

    JSONArray load() throws GeneralSecurityException, IOException, JSONException {
        byte[] sealed;
        try {
            sealed = storage.readFully();
        } catch (FileNotFoundException absent) {
            return new JSONArray();
        }
        if (sealed.length < IV_BYTES + TAG_BYTES) throw new IOException("Truncated encrypted cache");
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, key(), new GCMParameterSpec(128, sealed, 0, IV_BYTES));
        byte[] plain = cipher.doFinal(sealed, IV_BYTES, sealed.length - IV_BYTES);
        return new JSONArray(new String(plain, StandardCharsets.UTF_8));
    }
}
