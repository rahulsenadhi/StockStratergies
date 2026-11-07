"use client";

interface SegmentedProps<T extends string> {
  options: readonly T[];
  value: T;
  onChange: (value: T) => void;
  ariaLabel: string;
}

/** Segmented switch (Streamlit st.segmented_control in the v2 look). */
export function Segmented<T extends string>({ options, value, onChange, ariaLabel }: SegmentedProps<T>) {
  return (
    <div className="desk-seg" role="group" aria-label={ariaLabel}>
      {options.map((opt) => (
        <button key={opt} type="button" aria-pressed={opt === value} onClick={() => onChange(opt)}>
          {opt}
        </button>
      ))}
    </div>
  );
}
