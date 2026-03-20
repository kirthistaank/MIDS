/**
 * BotIcon.jsx — ConfidenceOS geometric bot icon
 * Usage: <BotIcon size={36} />
 */

export default function BotIcon({ size = 36 }) {
    const s = size;
    const cx = s / 2;
  
    // Scale factor based on original 72x72 design
    const sc = s / 72;
    const t = (v) => v * sc;
  
    return (
      <svg width={s} height={s} viewBox={`0 0 ${s} ${s}`} fill="none">
        {/* Hexagon head */}
        <polygon
          points={`${t(36)},${t(10)} ${t(52)},${t(19)} ${t(52)},${t(37)} ${t(36)},${t(46)} ${t(20)},${t(37)} ${t(20)},${t(19)}`}
          fill="#050f05"
          stroke="#22c55e"
          strokeWidth={t(1.5)}
        />
        {/* Antenna */}
        <line x1={t(36)} y1={t(10)} x2={t(36)} y2={t(5)} stroke="#22c55e" strokeWidth={t(1.5)} />
        <circle cx={t(36)} cy={t(4)} r={t(2)} fill="#22c55e" />
        {/* LED eyes */}
        <rect x={t(26)} y={t(23)} width={t(6)} height={t(4)} rx={t(1)} fill="#22c55e" />
        <rect x={t(40)} y={t(23)} width={t(6)} height={t(4)} rx={t(1)} fill="#22c55e" />
        {/* Mouth */}
        <rect x={t(28)} y={t(34)} width={t(16)} height={t(3)} rx={t(1.5)} fill="#22c55e" opacity="0.7" />
        {/* Body */}
        <rect x={t(27)} y={t(47)} width={t(18)} height={t(14)} rx={t(3)} fill="#050f05" stroke="#22c55e" strokeWidth={t(1.2)} />
        {/* Chest light */}
        <circle cx={t(36)} cy={t(54)} r={t(3)} fill="#22c55e" opacity="0.6" />
        {/* Arms */}
        <line x1={t(27)} y1={t(52)} x2={t(20)} y2={t(56)} stroke="#22c55e" strokeWidth={t(1.2)} strokeLinecap="round" />
        <line x1={t(45)} y1={t(52)} x2={t(52)} y2={t(56)} stroke="#22c55e" strokeWidth={t(1.2)} strokeLinecap="round" />
      </svg>
    );
  }