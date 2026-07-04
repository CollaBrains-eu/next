export default function LicensePlateInput({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="inline-flex overflow-hidden rounded-md border-2 border-black shadow-sm">
      <div className="flex w-7 flex-col items-center justify-end bg-blue-800 pb-1 pt-1 text-white">
        <span className="text-[9px] leading-none text-yellow-400">★★★</span>
        <span className="text-[11px] font-bold leading-none">NL</span>
      </div>
      <div className="flex items-center bg-yellow-400 px-3 py-1.5">
        <input
          value={value}
          onChange={(e) => onChange(e.target.value.toUpperCase())}
          placeholder="AB-12-CD"
          className="w-48 bg-transparent text-center font-sans text-2xl font-bold tracking-widest text-black placeholder:text-black/30 focus:outline-none"
        />
      </div>
    </div>
  );
}
