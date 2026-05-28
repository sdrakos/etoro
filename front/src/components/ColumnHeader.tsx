import type { Header } from "@tanstack/react-table";
import type { ScreenerRow } from "../types/screener";

interface Props {
  header: Header<ScreenerRow, unknown>;
  label: string;
}

export function ColumnHeader({ header, label }: Props) {
  const sorted = header.column.getIsSorted();
  const indicator = sorted === "asc" ? " ▲" : sorted === "desc" ? " ▼" : "";
  return (
    <th
      onClick={header.column.getToggleSortingHandler()}
      className="text-left text-xs font-medium text-fg-muted uppercase tracking-wider px-3 py-2 cursor-pointer select-none hover:text-fg-default"
      scope="col"
    >
      {label}{indicator}
    </th>
  );
}
