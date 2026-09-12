'use client';

// El puente entre las dos mitades de la pantalla.
//
// Arriba está el análisis —el gráfico, sus filtros, la ficha del activo— y
// abajo el explorador territorial. Son dos bloques separados por media pantalla
// de scroll y hasta ahora no se hablaban: se podía llegar a "Bandurria Sur"
// bajando por Neuquén y ahí el recorrido se terminaba, porque para verla en el
// gráfico había que subir, cambiar la dimensión a concesión y buscarla en una
// lista de 52.
//
// Este contexto transporta un pedido —"abrí esto en el análisis"— y nada más.
// No es un store de la pantalla: el estado del gráfico sigue viviendo en el
// módulo de análisis, que es quien lo usa. Acá solo viaja la intención, con un
// número de serie para que dos pedidos iguales seguidos —hacer clic dos veces
// en el mismo activo— se noten como dos pedidos y no como uno.

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';

import type { IdDimension } from '@/lib/produccion';

export interface PedidoEnfoque {
  dimension: IdDimension;
  /** El activo a seleccionar, o null si solo se pide el corte. */
  nombre: string | null;
  /** La concesión dentro de la cual mirar, cuando el pedido es un drill-down. */
  dentroDe: string | null;
  clave: number;
}

interface Contexto {
  pedido: PedidoEnfoque | null;
  enfocar: (pedido: Omit<PedidoEnfoque, 'clave'>) => void;
}

const ProduccionContexto = createContext<Contexto | null>(null);

export function ProveedorProduccion({ children }: { children: ReactNode }) {
  const [pedido, setPedido] = useState<PedidoEnfoque | null>(null);

  const enfocar = useCallback((nuevo: Omit<PedidoEnfoque, 'clave'>) => {
    setPedido({ ...nuevo, clave: Date.now() });
  }, []);

  const valor = useMemo(() => ({ pedido, enfocar }), [pedido, enfocar]);
  return <ProduccionContexto.Provider value={valor}>{children}</ProduccionContexto.Provider>;
}

/** Sin proveedor no rompe: devuelve un pedido vacío y un enfocar que no hace
 *  nada, así cualquiera de las dos piezas se puede montar sola. */
export function useProduccionUI(): Contexto {
  return useContext(ProduccionContexto) ?? { pedido: null, enfocar: () => {} };
}
