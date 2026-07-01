import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** shadcn-convention class combiner: clsx + tailwind-merge. */
export function cn(...inputs) {
  return twMerge(clsx(inputs));
}
