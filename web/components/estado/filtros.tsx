'use client';

// El estado compartido de la página: qué está filtrado y qué está en foco.
//
// Vive en un contexto y se refleja en la URL, así que una vista es un link. Eso
// es lo que separa una página de una plataforma: podés mandarle a alguien
// "mirá YPF entre 2024 y 2026 con el trimestre récord en foco" y le abre
// exactamente eso, sin explicarle dónde hacer clic.
//
// La sincronización con la URL se hace con history.replaceState y no con el
// router de Next a propósito: useSearchParams obliga a la página a renderizarse
// del lado del cliente, y esta página se prerenderiza entera con los datos
// adentro. No vale la pena pagar eso por cuatro parámetros.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

export interface Filtros {
  /** Nombre comercial del operador, o 'todos'. */
  operador: string;
  /** Año de inicio del período mirado. */
  desde: number;
  hasta: number;
  soloVacaMuerta: boolean;
  /** Trimestre en foco por clic, formato 2026Q2. Null es "ninguno". */
  foco: string | null;
}

export const RANGO_ANIOS = { min: 2019, max: 2026 } as const;

const INICIAL: Filtros = {
  operador: 'todos',
  desde: RANGO_ANIOS.min,
  hasta: RANGO_ANIOS.max,
  soloVacaMuerta: false,
  foco: null,
};

interface Contexto {
  filtros: Filtros;
  aplicar: (cambio: Partial<Filtros>) => void;
  limpiar: () => void;
  /** Hay algo distinto del estado inicial: sirve para ofrecer "limpiar". */
  activos: boolean;
  /** true si el trimestre entra en el período elegido. */
  enRango: (trimestre: string) => boolean;
}

const FiltrosContexto = createContext<Contexto | null>(null);

const CLAVES: Record<keyof Filtros, string> = {
  operador: 'op',
  desde: 'desde',
  hasta: 'hasta',
  soloVacaMuerta: 'vm',
  foco: 'foco',
};

function leerDeUrl(): Partial<Filtros> {
  if (typeof window === 'undefined') return {};
  const params = new URLSearchParams(window.location.search);
  const salida: Partial<Filtros> = {};

  const operador = params.get(CLAVES.operador);
  if (operador) salida.operador = operador;

  const desde = Number(params.get(CLAVES.desde));
  if (Number.isFinite(desde) && desde >= RANGO_ANIOS.min) salida.desde = desde;

  const hasta = Number(params.get(CLAVES.hasta));
  if (Number.isFinite(hasta) && hasta <= RANGO_ANIOS.max && hasta > 0) salida.hasta = hasta;

  if (params.get(CLAVES.soloVacaMuerta) === '1') salida.soloVacaMuerta = true;

  const foco = params.get(CLAVES.foco);
  if (foco && /^\d{4}Q[1-4]$/.test(foco)) salida.foco = foco;

  return salida;
}

function escribirEnUrl(filtros: Filtros) {
  const params = new URLSearchParams(window.location.search);
  const asignar = (clave: string, valor: string | null) => {
    if (valor === null) params.delete(clave);
    else params.set(clave, valor);
  };

  asignar(CLAVES.operador, filtros.operador === INICIAL.operador ? null : filtros.operador);
  asignar(CLAVES.desde, filtros.desde === INICIAL.desde ? null : String(filtros.desde));
  asignar(CLAVES.hasta, filtros.hasta === INICIAL.hasta ? null : String(filtros.hasta));
  asignar(CLAVES.soloVacaMuerta, filtros.soloVacaMuerta ? '1' : null);
  asignar(CLAVES.foco, filtros.foco);

  const consulta = params.toString();
  const url = `${window.location.pathname}${consulta ? `?${consulta}` : ''}${window.location.hash}`;
  window.history.replaceState(null, '', url);
}

export function ProveedorFiltros({ children }: { children: ReactNode }) {
  const [filtros, setFiltros] = useState<Filtros>(INICIAL);

  // La URL se lee una sola vez al montar. Hacerlo en el estado inicial rompería
  // la hidratación: el servidor no tiene querystring y pintaría otra cosa.
  useEffect(() => {
    const desdeUrl = leerDeUrl();
    if (Object.keys(desdeUrl).length) setFiltros((previo) => ({ ...previo, ...desdeUrl }));
  }, []);

  const aplicar = useCallback((cambio: Partial<Filtros>) => {
    setFiltros((previo) => {
      const siguiente = { ...previo, ...cambio };
      // Un rango invertido no es un estado válido: si mueven el piso por encima
      // del techo, el techo lo acompaña en vez de dejar la vista vacía.
      if (siguiente.desde > siguiente.hasta) {
        if (cambio.desde !== undefined) siguiente.hasta = siguiente.desde;
        else siguiente.desde = siguiente.hasta;
      }
      escribirEnUrl(siguiente);
      return siguiente;
    });
  }, []);

  const limpiar = useCallback(() => {
    setFiltros(INICIAL);
    escribirEnUrl(INICIAL);
  }, []);

  const valor = useMemo<Contexto>(() => {
    const activos =
      filtros.operador !== INICIAL.operador ||
      filtros.desde !== INICIAL.desde ||
      filtros.hasta !== INICIAL.hasta ||
      filtros.soloVacaMuerta ||
      filtros.foco !== null;

    const enRango = (trimestre: string) => {
      const anio = Number(trimestre.slice(0, 4));
      return anio >= filtros.desde && anio <= filtros.hasta;
    };

    return { filtros, aplicar, limpiar, activos, enRango };
  }, [filtros, aplicar, limpiar]);

  return <FiltrosContexto.Provider value={valor}>{children}</FiltrosContexto.Provider>;
}

export function useFiltros(): Contexto {
  const contexto = useContext(FiltrosContexto);
  if (!contexto) throw new Error('useFiltros necesita estar dentro de ProveedorFiltros');
  return contexto;
}

/** Los paneles que solo tienen datos de YPF avisan en vez de mentir. */
export function soloYPF(operador: string): boolean {
  return operador !== 'todos' && operador !== 'YPF';
}
