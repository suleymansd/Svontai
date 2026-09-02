import * as Crypto from 'expo-crypto';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

const REFRESH_TOKEN_KEY = 'svontai.mobile.refresh-token';
const DEVICE_ID_KEY = 'svontai.mobile.device-id';
let webDeviceId: string | null = null;
let webRefreshToken: string | null = null;

const secureOptions: SecureStore.SecureStoreOptions = {
  keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
};

export async function getOrCreateDeviceId(): Promise<string> {
  if (Platform.OS === 'web') {
    webDeviceId ??= Crypto.randomUUID();
    return webDeviceId;
  }

  const stored = await SecureStore.getItemAsync(DEVICE_ID_KEY, secureOptions);
  if (stored) return stored;

  const deviceId = Crypto.randomUUID();
  await SecureStore.setItemAsync(DEVICE_ID_KEY, deviceId, secureOptions);
  return deviceId;
}

export function getRefreshToken(): Promise<string | null> {
  if (Platform.OS === 'web') return Promise.resolve(webRefreshToken);
  return SecureStore.getItemAsync(REFRESH_TOKEN_KEY, secureOptions);
}

export function setRefreshToken(token: string): Promise<void> {
  if (Platform.OS === 'web') {
    webRefreshToken = token;
    return Promise.resolve();
  }
  return SecureStore.setItemAsync(REFRESH_TOKEN_KEY, token, secureOptions);
}

export function clearRefreshToken(): Promise<void> {
  if (Platform.OS === 'web') {
    webRefreshToken = null;
    return Promise.resolve();
  }
  return SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY, secureOptions);
}
