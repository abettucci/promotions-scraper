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
  if (!validDays) return <span className="text-[11px] text-[#71839a]">Todos los días</span>

  const today = todayEs()
  const days = Object.keys(DAY_SHORT)

  const activeDays = days.filter((d) =>
    validDays.toLowerCase().includes(d)
  )

  if (activeDays.length === 0) {
    return <span className="max-w-[180px] truncate text-[11px] text-[#52657d]">{validDays}</span>
  }

  return (
    <span className="inline-flex flex-wrap gap-1">
      {activeDays.map((d) => {
        const isToday = d === today || (d === "miercoles" && today === "miércoles")
        return (
          <span
            key={d}
            className={clsx(
              "rounded-md px-1.5 py-0.5 text-[10px] font-semibold",
              isToday
                ? "bg-[#102a4c] text-[#b8f36b]"
                : "bg-[#edf2f7] text-[#52657d]"
            )}
          >
            {DAY_SHORT[d]}
          </span>
        )
      })}
    </span>
  )
}
