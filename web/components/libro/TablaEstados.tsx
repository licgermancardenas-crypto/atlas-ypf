'use client';

// Los tres estados contables, con el comportamiento de una planilla.
//
// Es la parte del módulo que reemplaza al Excel para el noventa por ciento de
// las consultas: elegir el estado, elegir si se mira por trimestre o por
// ejercicio, buscar una línea y recorrerla con el dedo. Lo que el Excel hace
// mejor —copiar un rango, pegarlo en otro modelo— sigue estando a un clic, en
// el botón de descarga.

import { useMemo, useState } from 'react';

import { TablaExcel, type FilaExcel } from '@/components/TablaExcel';
import { fmt } from '@/lib/data';
import type { Estados } from '@/lib/libro';

const ESTADOS: { id: string; etiqueta: string }[] = [
  { id: 'resultados', etiqueta: 'Resultados' },
  { id: 'balance', etiqueta: 'Balance' },
  { id: 'flujo', etiqueta: 'Flujo de efectivo' },
];

type Vista = 'trimestral' | 'anual';

export function TablaEstados({ estados }: { estados: Estados }) {
  const [estado, setEstado] = useState('resultados');
  const [vista, setVista] = useState<Vista>('trimestral');
  const [busqueda, setBusqueda] = useState('');
  const [enIngles, setEnIngles] = useState(false);

  const bloque = estados.estados[estado];
  const columnas = vista === 'trimestral' ? estados.trimestres : estados.anios;

  const filas: FilaExcel[] = useMemo(() => {
    if (!bloque) return [];
    const texto = busqueda.trim().toLowerCase();
    return bloque.lineas
      .filter((linea) => {
        const valores = vista === 'trimestral' ? linea.trimestral : linea.anual;
        if (!valores.some((valor) => valor !== null)) return false;
        if (!texto) return true;
        return (
          linea.etiqueta.toLowerCase().includes(texto) ||
          linea.original.toLowerCase().includes(texto)
        );
      })
      .map((linea) => ({
        concepto: enIngles ? linea.original : linea.etiqueta,
        ayuda: enIngles ? linea.etiqueta : linea.original,
        subtotal: linea.total,
        formato: 'entero' as const,
        marcas: vista === 'trimestral' ? marcasDe(linea.derivacion, linea.moneda) : undefined,
        valores: vista === 'trimestral' ? linea.trimestral : linea.anual,
      }));
  }, [bloque, busqueda, enIngles, vista]);

  const columnasVisibles = columnas.map((columna) =>
    vista === 'trimestral' ? fmt.trimestre(columna) : columna,
  );

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex rounded-md border border-borde p-0.5">
          {ESTADOS.map((opcion) => (
            <button
              key={opcion.id}
              type="button"
              onClick={() => setEstado(opcion.id)}
              className={`rounded px-3 py-1.5 text-xs transition-colors ${
                estado === opcion.id
                  ? 'bg-superficie-alta text-texto'
                  : 'text-texto-suave hover:text-texto'
              }`}
            >
              {opcion.etiqueta}
            </button>
          ))}
        </div>

        <div className="flex rounded-md border border-borde p-0.5">
          {(['trimestral', 'anual'] as Vista[]).map((opcion) => (
            <button
              key={opcion}
              type="button"
              onClick={() => setVista(opcion)}
              className={`rounded px-3 py-1.5 text-xs capitalize transition-colors ${
                vista === opcion ? 'bg-superficie-alta text-texto' : 'text-texto-suave hover:text-texto'
              }`}
            >
              {opcion}
            </button>
          ))}
        </div>

        <input
          value={busqueda}
          onChange={(evento) => setBusqueda(evento.target.value)}
          placeholder="Buscar una línea…"
          className="min-w-[12rem] flex-1 rounded-md border border-borde bg-fondo px-3 py-1.5 text-xs text-texto placeholder:text-texto-tenue"
        />

        <label className="flex items-center gap-1.5 text-xs text-texto-suave">
          <input
            type="checkbox"
            checked={enIngles}
            onChange={() => setEnIngles((previo) => !previo)}
            className="accent-[#0054eb]"
          />
          Como lo publica
        </label>
      </div>

      <p className="mt-2 text-[0.7rem] leading-relaxed text-texto-tenue">
        {bloque?.titulo} · en millones de dólares · {filas.length} líneas.{' '}
        <span className="italic">En bastardilla</span>, los trimestres que salen por diferencia de
        acumulados; <span className="text-oro/90">en marrón</span>, los que la compañía presentó en
        pesos y vuelven a dólares al tipo de cambio con el que se tradujeron.
      </p>

      <div className="mt-3">
        <TablaExcel
          columnas={columnasVisibles}
          filas={filas}
          etiquetaPrimera="US$ millones"
          anchoPrimera="22rem"
        />
      </div>
    </div>
  );
}

/** Una sola cadena de marcas por fila: la moneda manda sobre la derivación,
 *  porque un trimestre traducido y derivado es, sobre todo, traducido. */
function marcasDe(derivacion: string, moneda: string): string {
  return Array.from(derivacion)
    .map((letra, indice) => (moneda[indice] === 'A' ? 'A' : letra))
    .join('');
}
