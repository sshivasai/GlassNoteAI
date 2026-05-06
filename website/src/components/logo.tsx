import Image from "next/image";

export function Logo({ className }: { className?: string }) {
  return <Image src="/Logo.png" alt="Logo" width={40} height={40} className={className} />;
}
