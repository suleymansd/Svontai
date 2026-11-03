import { useQueryClient } from '@tanstack/react-query';
import { createParser } from 'eventsource-parser';
import { createContext, useContext, useEffect, useState } from 'react';
import { AppState } from 'react-native';

import { openRealtimeStream } from './client';

export const RealtimeContext = createContext(false);
export const useRealtimeConnected = () => useContext(RealtimeContext);

export function useMobileRealtime(enabled: boolean): boolean {
  const queryClient = useQueryClient();
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!enabled) return;
    let disposed = false;
    let controller: AbortController | null = null;
    let retry: ReturnType<typeof setTimeout> | null = null;
    let invalidate: ReturnType<typeof setTimeout> | null = null;
    let backoff = 1000;
    const refresh = () => {
      if (invalidate) return;
      invalidate = setTimeout(() => {
        invalidate = null;
        void queryClient.invalidateQueries({ queryKey: ['conversations'] });
        void queryClient.invalidateQueries({ queryKey: ['conversation-messages'] });
        void queryClient.invalidateQueries({ queryKey: ['operator-deliveries'] });
      }, 250);
    };
    const connect = async () => {
      if (disposed || AppState.currentState !== 'active') return;
      const active = new AbortController();
      controller = active;
      let watchdog: ReturnType<typeof setTimeout>;
      const resetWatchdog = () => {
        clearTimeout(watchdog);
        watchdog = setTimeout(() => active.abort(), 40_000);
      };
      resetWatchdog();
      try {
        const response = await openRealtimeStream(active.signal);
        if (!response.body) throw new Error('Empty event stream');
        if (active.signal.aborted) return;
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        const parser = createParser({ maxBufferSize: 65_536, onError: () => active.abort(), onEvent: ({ data }) => {
          try {
            const payload = JSON.parse(data);
            if (payload.type === 'ready') {
              setConnected(payload.live !== false);
              backoff = 1000;
              refresh();
            } else if (typeof payload.type === 'string' && /^(message|conversation)\./.test(payload.type)) refresh();
          } catch { /* A malformed event must not terminate the session. */ }
        } });
        while (!active.signal.aborted) {
          const { done, value } = await reader.read();
          if (done) break;
          resetWatchdog();
          parser.feed(decoder.decode(value, { stream: true }));
        }
      } catch { /* Backoff and the foreground-only fallback query recover. */ }
      finally {
        clearTimeout(watchdog!);
        active.abort();
        if (controller === active) {
          setConnected(false);
          if (!disposed && AppState.currentState === 'active') {
            retry = setTimeout(() => void connect(), backoff + Math.random() * 500);
            backoff = Math.min(backoff * 2, 30_000);
          }
        }
      }
    };
    const stop = () => {
      if (retry) clearTimeout(retry);
      const active = controller;
      controller = null;
      active?.abort();
      setConnected(false);
    };
    const subscription = AppState.addEventListener('change', (state) => {
      stop();
      if (state === 'active') void connect();
    });
    void connect();
    return () => {
      disposed = true;
      stop();
      subscription.remove();
      if (invalidate) clearTimeout(invalidate);
    };
  }, [enabled, queryClient]);
  return enabled && connected;
}
