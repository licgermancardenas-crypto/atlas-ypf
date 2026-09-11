// La tira de indicadores: lo que hay que entender en cinco segundos.
//
// Cuatro tarjetas y una jerarquía adentro de cada una: etiqueta, número,
// unidad, variación y forma de la serie. El número manda; todo lo demás lo
// acompaña. La variación va contra los doce meses previos y lo dice, porque un
// "+6%" sin período es decoración.
//
// Es un componente de servidor: sale calculado del JSON liviano y se pinta con
// el HTML, sin esperar a que baje ninguna serie. Lo único que hace en el
// cliente es responder al hover, que es CSS.

import { fmt } from '@/lib/data';
import {
  chispa,
  clavesDe,
  compararUDM,
  COLOR,
  type ProduccionYPF,
} from '@/lib/produccion';
import { Chispa, Composicion } from './Chispa';

function Variacion({ valor, referencia }: { valor: number | null; referencia: string }) {
  if (valor === null) {
    return <span className="text-[0.7rem] text-texto-tenue">sin base de comparación</span>;
  }
  const sube = valor >= 0;
  return (
    <span
      className={`inline-flex items-center gap-1 text-[0.72rem] ${sube ? 'text-alza' : 'text-baja'}`}
    >
      {/* La flecha además del color: quien no distingue verde de naranja
          igual tiene que poder leer el signo. */}
      <span aria-hidden>{sube ? '▲' : '▼'}</span>
      {fmt.porcentajeConSigno(valor, 1)}
      <span className="text-texto-tenue">{referencia}</span>
    </span>
  );
}

function Tarjeta({
  etiqueta,
  valor,
  unidad,
  tono = 'texto',
  children,
  pie,
  href,
}: {
  etiqueta: string;
  valor: string;
  unidad?: string;
  tono?: 'texto' | 'oro' | 'celeste' | 'shale';
  children?: React.ReactNode;
  pie?: string;
  href?: string;
}) {
  const tonos = {
    texto: 'text-texto',
    oro: 'text-oro',
    celeste: 'text-celeste',
    shale: 'text-[color:var(--color-shale)]',
  } as const;

  const contenido = (
    <>
      <p className="font-mono text-[0.68rem] uppercase tracking-[0.14em] text-texto-tenue">
        {etiqueta}
      </p>
      <p className="mt-3 flex items-baseline gap-1.5">
        <span className={`tabular text-[1.75rem] font-semibold leading-none ${tonos[tono]}`}>
          {valor}
        </span>
        {unidad ? <span className="text-xs text-texto-suave">{unidad}</span> : null}
      </p>
      <div className="mt-2.5 min-h-[1.1rem]">{children}</div>
      {pie ? <p className="mt-2 text-[0.7rem] leading-snug text-texto-tenue">{pie}</p> : null}
    </>
  );

  const clases =
    'group block rounded-lg border border-borde bg-superficie p-4 transition-colors hover:border-borde-vivo focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-azul-claro';

  return href ? (
    <a href={href} className={clases}>
      {contenido}
    </a>
  ) : (
    <div className={clases}>{contenido}</div>
  );
}

export function Kpis({ datos }: { datos: ProduccionYPF }) {
  const comparacion = compararUDM(datos);
  const actual = comparacion?.actual;
  const referencia = 'i.a.';

  const petroleo = chispa(datos, clavesDe('oil', 'todo'));
  const gas = chispa(datos, clavesDe('gas', 'todo'));
  const shale = chispa(datos, clavesDe('boe', 'shale'));

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <Tarjeta
        etiqueta="Petróleo"
        valor={fmt.entero(actual?.oil ?? datos.resumen.petroleo_bd)}
        unidad="bbl/d"
        tono="oro"
        pie="Promedio diario de los últimos doce meses"
      >
        <div className="flex items-center justify-between gap-3">
          <Variacion valor={comparacion?.varOil ?? null} referencia={referencia} />
          <span className="w-20 shrink-0">
            <Chispa valores={petroleo.valores} color={COLOR.petroleo} alto={22} />
          </span>
        </div>
      </Tarjeta>

      <Tarjeta
        etiqueta="Gas"
        valor={fmt.entero(actual?.gas ?? datos.resumen.gas_boed)}
        unidad="boe/d"
        tono="celeste"
        pie={`${fmt.entero(actual?.boe ?? 0)} boe/d entre los dos fluidos`}
      >
        <div className="flex items-center justify-between gap-3">
          <Variacion valor={comparacion?.varGas ?? null} referencia={referencia} />
          <span className="w-20 shrink-0">
            <Chispa valores={gas.valores} color={COLOR.gas} alto={22} />
          </span>
        </div>
      </Tarjeta>

      <Tarjeta
        etiqueta="Shale sobre el total"
        valor={fmt.porcentaje(actual?.shareShale ?? null, 0)}
        tono="shale"
        pie={`Convencional ${fmt.entero(actual?.convencional ?? 0)} · tight ${fmt.entero(
          actual?.tight ?? 0,
        )} boe/d`}
      >
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-3">
            {comparacion?.deltaShale !== null && comparacion?.deltaShale !== undefined ? (
              <span
                className={`text-[0.72rem] ${comparacion.deltaShale >= 0 ? 'text-alza' : 'text-baja'}`}
              >
                <span aria-hidden>{comparacion.deltaShale >= 0 ? '▲' : '▼'}</span>{' '}
                {fmt.numero(Math.abs(comparacion.deltaShale) * 100, 1)} p.p.{' '}
                <span className="text-texto-tenue">{referencia}</span>
              </span>
            ) : (
              <span className="text-[0.7rem] text-texto-tenue">sin base de comparación</span>
            )}
            <span className="w-20 shrink-0">
              <Chispa valores={shale.valores} color={COLOR.shale} alto={22} />
            </span>
          </div>
          <Composicion
            etiqueta="Composición por tipo de roca: shale, convencional y tight"
            partes={[
              { nombre: 'Shale', valor: actual?.shale ?? 0, color: COLOR.shale },
              { nombre: 'Convencional', valor: actual?.convencional ?? 0, color: COLOR.convencional },
              { nombre: 'Tight', valor: actual?.tight ?? 0, color: COLOR.tight },
            ]}
          />
        </div>
      </Tarjeta>

      <Tarjeta
        etiqueta="Dónde"
        valor={String(datos.resumen.concesiones)}
        unidad="concesiones"
        href="#donde"
        pie="Ver el detalle territorial"
      >
        <p className="text-[0.72rem] text-texto-suave">
          {datos.resumen.yacimientos} yacimientos · {datos.resumen.provincias} provincias ·{' '}
          {datos.resumen.cuencas} cuencas
        </p>
      </Tarjeta>
    </div>
  );
}
