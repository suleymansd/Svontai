import { Image, StyleSheet, Text, View } from 'react-native';

import { palette } from '@/constants/theme';

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <View style={styles.row}>
      <Image
        source={require('@/assets/images/svontai-logo.png')}
        resizeMode="contain"
        style={compact ? styles.iconSmall : styles.icon}
      />
      <Text style={compact ? styles.textSmall : styles.text}>SvontAI</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  icon: { width: 44, height: 44 },
  iconSmall: { width: 30, height: 30 },
  text: { fontSize: 27, fontWeight: '800', color: palette.navy },
  textSmall: { fontSize: 20, fontWeight: '800', color: palette.navy },
});
