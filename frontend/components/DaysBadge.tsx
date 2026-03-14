"use client"

import { clsx } from "clsx"

const DAY_SHORT: Record<string, string> = {
  lunes: "Lun", martes: "Mar", "miércoles": "Mié", miercoles: "Mié",
  jueves: "Jue", viernes: "Vie", "sábado": "Sáb", sabado: "Sáb",
  domingo: "Dom",
}

const TODAY_ES: Record<string, string> = {
  Monday: "lunes", Tuesday: "martes", Wednesday: "miércoles",
  Thursday: "jueves", Friday: "viernes", Saturday: "sábado", Sunday: "domingo",
}

function todayEs() {
  return TODAY_ES[new Date().toLocaleDateString("en-US", { weekday: "long" })] ?? ""
}

interface Props {
  validDays: string | null | undefined
}

export function DaysBadge({ validDays }: Props) {
  if (!validDays) return <span className="text-[11px] text-slate-400">Todos los días</span>

  const today = todayEs()
  const days = Object.keys(DAY_SHORT)

  const activeDays = days.filter((d) =>
    validDays.toLowerCase().includes(d)
  )

  if (activeDays.length === 0) {
    return <span className="text-[11px] text-slate-500 truncate max-w-[180px]">{validDays}</span>
  }

  return (
    <span className="inline-flex flex-wrap gap-1">
      {activeDays.map((d) => {
        const isToday = d === today || (d === "miercoles" && today === "miércoles")
        return (
          <span
            key={d}
            className={clsx(
              "text-[10px] font-semibold px-1.5 py-0.5 rounded",
              isToday
                ? "bg-emerald-500 text-white"
                : "bg-slate-100 text-slate-600"
            )}
          >
            {DAY_SHORT[d]}
          </span>
        )
      })}
    </span>
  )
}
