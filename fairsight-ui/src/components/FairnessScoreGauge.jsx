import React from 'react'

/**
 * FairnessScoreGauge
 * =================
 * A visual "speedometer" style gauge for the fairness score (1 - |DPD|).
 */
export default function FairnessScoreGauge({ score, label, beforeScore = null }) {
  const percentage = Math.min(Math.max(score * 100, 0), 100)
  
  // Determine color based on score
  let color = '#DC2626' // Red (High Bias)
  let status = 'High Bias'
  if (score >= 0.8) {
    color = '#16A34A' // Green (Fair)
    status = 'Fair'
  } else if (score >= 0.5) {
    color = '#F59E0B' // Amber (Moderate)
    status = 'Moderate'
  }

  const rotation = (score * 180) - 90 // -90 to +90 degrees

  return (
    <div className="flex flex-col items-center p-4 bg-white border border-gray-100 rounded-2xl shadow-sm">
      <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">{label}</p>
      
      <div className="relative w-48 h-24 overflow-hidden flex items-end justify-center">
        {/* Gauge Track */}
        <div className="absolute inset-0 border-[12px] border-gray-100 rounded-t-full w-48 h-48 top-0"></div>
        
        {/* Progress Track */}
        <div 
          className="absolute inset-0 border-[12px] rounded-t-full w-48 h-48 top-0 transition-all duration-1000 ease-out"
          style={{ 
            borderColor: color,
            clipPath: `inset(0 ${100 - (percentage/2)}% 0 0)`, // This is a bit tricky for arcs, let's use a simpler SVG
          }}
        ></div>

        {/* SVG version for better accuracy */}
        <svg viewBox="0 0 100 50" className="w-48 h-24 absolute top-0 left-0">
          <path
            d="M 10 50 A 40 40 0 0 1 90 50"
            fill="none"
            stroke="#F3F4F6"
            strokeWidth="8"
          />
          <path
            d="M 10 50 A 40 40 0 0 1 90 50"
            fill="none"
            stroke={color}
            strokeWidth="8"
            strokeDasharray="125.6"
            strokeDashoffset={125.6 * (1 - score)}
            className="transition-all duration-1000 ease-out"
          />
        </svg>

        <div className="flex flex-col items-center z-10 pb-2">
          <span className="text-3xl font-black text-gray-900 leading-none">{(score * 10).toFixed(1)}</span>
          <span className="text-[10px] font-bold text-gray-400 mt-1 uppercase">Score</span>
        </div>
      </div>

      <div className="mt-4 flex items-center gap-2">
         <div className="h-2 w-2 rounded-full" style={{ backgroundColor: color }}></div>
         <span className="text-xs font-bold uppercase tracking-wide" style={{ color }}>{status}</span>
      </div>

      {beforeScore !== null && (
        <div className="mt-3 pt-3 border-t border-gray-50 w-full text-center">
           <p className="text-[10px] text-gray-400">
             Before: <span className="font-mono font-bold text-gray-600">{(beforeScore * 10).toFixed(1)}</span>
             {' → '}
             <span className="text-green-600 font-bold">+{((score - beforeScore) * 10).toFixed(1)} improvement</span>
           </p>
        </div>
      )}
    </div>
  )
}
