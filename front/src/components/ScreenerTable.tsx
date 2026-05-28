import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { useMemo, useState } from "react";
import type { ScreenerRow } from "../types/screener";
import {
  formatMoney,
  formatPercent,
  formatVolume,
  formatPE,
  changeColorClass,
} from "../lib/formatters";
import { ColumnHeader } from "./ColumnHeader";

interface Props {
  rows: ScreenerRow[];
  filter: string;
}

export function ScreenerTable({ rows, filter }: Props) {
  const [sorting, setSorting] = useState<SortingState>([]);

  const columns = useMemo<ColumnDef<ScreenerRow>[]>(
    () => [
      { accessorKey: "ticker", header: "Ticker",
        cell: (info) => <span className="font-mono font-medium">{info.getValue() as string}</span> },
      { accessorKey: "name", header: "Name",
        cell: (info) => <span className="text-fg-default">{info.getValue() as string}</span> },
      { accessorKey: "sector", header: "Sector",
        cell: (info) => <span className="text-fg-muted text-sm">{info.getValue() as string}</span> },
      { accessorKey: "price", header: "Price",
        cell: (info) => {
          const v = info.getValue() as number | null;
          return v === null || v === undefined ? "—" : `$${v.toFixed(2)}`;
        } },
      { accessorKey: "change_pct", header: "Chg %",
        cell: (info) => {
          const v = info.getValue() as number | null;
          return <span className={changeColorClass(v)}>{formatPercent(v)}</span>;
        } },
      { accessorKey: "volume", header: "Volume",
        cell: (info) => formatVolume(info.getValue() as number | null) },
      { accessorKey: "market_cap", header: "Mkt Cap",
        cell: (info) => formatMoney(info.getValue() as number | null) },
      { accessorKey: "pe_ratio", header: "P/E",
        cell: (info) => formatPE(info.getValue() as number | null) },
    ],
    []
  );

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting, globalFilter: filter },
    sortDescFirst: false,
    onSortingChange: setSorting,
    globalFilterFn: (row, _columnId, filterValue: string) => {
      const q = filterValue.toLowerCase();
      return (
        row.original.ticker.toLowerCase().includes(q) ||
        row.original.name.toLowerCase().includes(q)
      );
    },
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  return (
    <div className="overflow-auto border border-border-default rounded-md">
      <table className="min-w-full divide-y divide-border-default">
        <thead className="bg-bg-surface sticky top-0">
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {hg.headers.map((h) => (
                <ColumnHeader key={h.id} header={h} label={h.column.columnDef.header as string} />
              ))}
            </tr>
          ))}
        </thead>
        <tbody className="divide-y divide-border-default bg-bg-base">
          {table.getRowModel().rows.map((row) => (
            <tr key={row.id} className="hover:bg-bg-surface">
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id} className="px-3 py-1.5 text-sm whitespace-nowrap">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
