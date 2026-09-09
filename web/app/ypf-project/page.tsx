import Link from 'next/link';

import {
  AccionYRiesgoPais,
  CurvasTipo,
  ProduccionPorOperador,
  Puente,
  ReaccionBalances,
  ShaleYCostos,
} from '@/components/charts';
import { MapaCuenca } from '@/components/mapa/MapaCuenca';
import { PanelFinanciero } from '@/components/PanelFinanciero';
import { Shell } from '@/components/Shell';
import { Simulador } from '@/components/Simulador';
import { Dato, Franja, Nota, Seccion, Tabla, Tarjeta } from '@/components/ui';
import { cargar } from '@/lib/server-data';
import {
  fmt,
  type CurvasDeclive,
  type Economia,
  type Financieros,
  type Mercado,
  type Produccion,
  type Sensibilidad,
} from '@/lib/data';

// La página se arma en el servidor con los JSON del pipeline ya adentro: el
// primer render trae los números, y lo único que el browser va a buscar después
// son las capas del mapa, que pesan y no hacen falta para leer la tesis.
export default async function CasoYPF() {
  const [financieros, sensibilidad, mercado, produccion, economia, declive] = await Promise.all([
    cargar<Financieros>('financials_ypf.json'),
    cargar<Sensibilidad>('ebitda_sensitivity.json'),
    cargar<Mercado>('market_reaction.json'),
    cargar<Produccion>('production_summary.json'),
    cargar<Economia>('well_economics.json'),
    cargar<CurvasDeclive>('decline_type_curves.json'),
  ]);

  const ultimo = financieros.serie[financieros.serie.length - 1];
  const previoAnual = financieros.serie[financieros.serie.length - 5];
  const evento = mercado.eventos[mercado.eventos.length - 1];
  const puente = sensibilidad.descomposicion_ultimo_trimestre;
  const coefEbitda = sensibilidad.modelo_operativo.coeficientes;
  const coef = (variable: string) =>
    coefEbitda.find((elemento) => elemento.variable === variable);

  const variacion = (actual: number | null, anterior: number | null) =>
    actual !== null && anterior !== null && anterior !== 0 ? actual / anterior - 1 : null;

  return (
    <Shell actualizado={financieros.generado.slice(0, 10)}>
      <main className="pb-24">

      {/* ------------------------------------------------------------------ */}
      <header className="border-b border-borde">
        <div className="mx-auto max-w-6xl px-6 py-14 sm:py-20">
          <Franja className="w-24" />
          <p className="mt-5 font-mono text-xs tracking-[0.2em] text-azul-claro">
            ATLAS-YPF · CASO DE ESTUDIO · {fmt.trimestre(ultimo.trimestre)}
          </p>
          <h1 className="mt-5 max-w-3xl text-3xl font-bold leading-[1.1] sm:text-5xl">
            YPF publicó el mejor trimestre de su historia.
            <br />
            <span className="text-texto-suave">El mercado lo vendió.</span>
          </h1>

          {/* La confrontación: los dos números que son la tesis del caso. El
              resto de la página existe para explicar por qué conviven. */}
          <div className="mt-10 flex flex-col gap-6 sm:flex-row sm:items-stretch sm:gap-0">
            <div className="sm:pr-10">
              <p className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-texto-tenue">
                EBITDA ajustado, interanual
              </p>
              <p className="tabular mt-1 text-5xl font-semibold text-azul-claro sm:text-6xl">
                {fmt.porcentajeConSigno(
                  variacion(ultimo.adj_ebitda_musd, previoAnual.adj_ebitda_musd),
                  0,
                )}
              </p>
              <p className="mt-1 text-sm text-texto-suave">
                {fmt.musd(ultimo.adj_ebitda_musd)} en el trimestre
              </p>
            </div>

            <div className="hidden w-px bg-borde sm:block" aria-hidden="true" />

            <div className="sm:pl-10">
              <p className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-texto-tenue">
                La acción, ese mismo día
              </p>
              <p className="tabular mt-1 text-5xl font-semibold text-baja sm:text-6xl">
                {fmt.porcentajeConSigno(evento.retorno_dia)}
              </p>
              <p className="mt-1 text-sm text-texto-suave">
                {fmt.porcentajeConSigno(evento.retorno_anormal_dia)} descontando sector y Brent
              </p>
            </div>
          </div>

          <p className="mt-10 max-w-2xl leading-relaxed text-texto-suave">
            Deuda neta en el mínimo de la serie, el shale creciendo 47% y el costo de extracción en
            un tercio menos que hace dos años. Este caso reconstruye por qué el precio no acompañó,
            cruzando el balance con la producción pozo por pozo, el crudo y el riesgo país.
          </p>

          <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Dato
              etiqueta="Shale oil"
              valor={`${fmt.decimal(ultimo.shale_oil_kbbld)} Kbbl/d`}
              delta={variacion(ultimo.shale_oil_kbbld, previoAnual.shale_oil_kbbld)}
              deltaReferencia=" i.a."
              detalle="producción neta que reporta la compañía"
              tono="alza"
            />
            <Dato
              etiqueta="Deuda neta / EBITDA"
              valor={`${fmt.decimal(ultimo.net_leverage_x)}x`}
              delta={variacion(ultimo.net_leverage_x, previoAnual.net_leverage_x)}
              deltaReferencia=" i.a."
              detalle={`deuda neta ${fmt.musd(ultimo.net_debt_musd)}`}
              tono="marca"
            />
            <Dato
              etiqueta="Lifting cost"
              valor={`US$ ${fmt.numero(ultimo.lifting_cost_usd_boe, 1)}/boe`}
              delta={variacion(ultimo.lifting_cost_usd_boe, previoAnual.lifting_cost_usd_boe)}
              deltaReferencia=" i.a."
              detalle="desde US$ 16 en 2024"
              tono="crudo"
            />
            <Dato
              etiqueta="Sin explicar en el trimestre"
              valor={fmt.musd(puente.residual_musd)}
              detalle="del salto de EBITDA contra el trimestre anterior"
              tono="crudo"
            />
          </div>
        </div>
      </header>

      {/* ------------------------------------------------------------------ */}
      <Seccion
        id="balance"
        numero="01"
        titulo="El balance, sin adjetivos"
        bajada={
          <>
            Veintisiete trimestres reconstruidos desde los earnings releases que YPF adjunta a cada
            6-K en la SEC. El XBRL de EDGAR solo tiene los anuales, así que el dato trimestral hubo
            que parsearlo de la tabla de highlights, cuyo formato cambió tres veces desde 2021.
          </>
        }
      >
        <Tarjeta titulo="La serie trimestral, contra el Brent promedio del trimestre">
          <PanelFinanciero serie={sensibilidad.serie} />
          <Nota>
            Cada trimestre se toma del release donde es el trimestre titular, no de las columnas
            comparativas de reportes posteriores: el 2T22 quedó en los US$ 4.855M que YPF informó
            ese día y no en los US$ 4.995M reexpresados un año después. Lo que se está explicando es
            la reacción del mercado al dato de ese momento.
          </Nota>
        </Tarjeta>
      </Seccion>

      {/* ------------------------------------------------------------------ */}
      <Seccion
        id="origen"
        numero="02"
        titulo="De dónde salió el récord"
        bajada={
          <>
            Un modelo de cuatro drivers explica el {fmt.porcentaje(sensibilidad.modelo_operativo.r2, 0)}{' '}
            de la variación del EBITDA trimestral. Sirve para descomponer el salto del último
            trimestre en partes que se pueden atribuir — y en una que no.
          </>
        }
      >
        <div className="grid gap-6 lg:grid-cols-2">
          <Tarjeta titulo={`Puente del EBITDA: ${fmt.trimestre(puente.desde)} a ${fmt.trimestre(puente.hasta)}`}>
            <Puente descomposicion={puente} />
            <Nota>
              De los {fmt.musd(puente.delta_musd)} de mejora, el modelo atribuye{' '}
              {fmt.musd(puente.efecto_precio_musd)} al Brent (de US$ {fmt.decimal(puente.brent_previo)}{' '}
              a US$ {fmt.decimal(puente.brent_actual)}),{' '}
              {fmt.musd(puente.efecto_volumen_musd)} al volumen y{' '}
              {fmt.musd(puente.efecto_costo_musd + puente.efecto_downstream_musd)} a costos y
              downstream. Quedan {fmt.musd(puente.residual_musd)} sin explicar: casi la mitad del
              salto no se sigue de los drivers estructurales.
            </Nota>
          </Tarjeta>

          <Tarjeta titulo="Producción de shale y costo de extracción">
            <ShaleYCostos serie={sensibilidad.serie} />
            <Nota>
              El lifting cost cayó de US$ 16 a US$ {fmt.decimal(ultimo.lifting_cost_usd_boe)} por boe
              mientras el shale crecía. Sin esta variable en el modelo, el R² baja de{' '}
              {fmt.numero(sensibilidad.modelo_operativo.r2)} a 0,27 y el Brent se lleva un crédito que
              en realidad es de eficiencia operativa.
            </Nota>
          </Tarjeta>
        </div>

        <div className="mt-6">
          <Tarjeta titulo="Cuánto mueve cada driver el EBITDA de un trimestre">
            <Tabla
              columnas={[
                { clave: 'driver', titulo: 'Driver' },
                { clave: 'efecto', titulo: 'Efecto', alineacion: 'der' },
                { clave: 'intervalo', titulo: 'Intervalo 95%', alineacion: 'der' },
                { clave: 'p', titulo: 'p', alineacion: 'der' },
              ]}
              filas={[
                { variable: 'brent_usd', nombre: 'Brent', unidad: 'por US$/bbl' },
                { variable: 'produccion_kboed', nombre: 'Producción', unidad: 'por Kboe/d' },
                { variable: 'lifting_cost_usd_boe', nombre: 'Lifting cost', unidad: 'por US$/boe' },
                { variable: 'crudo_procesado_kbbld', nombre: 'Crudo procesado', unidad: 'por Kbbl/d' },
              ].map(({ variable, nombre, unidad }) => {
                const dato = coef(variable);
                return {
                  driver: (
                    <span>
                      {nombre} <span className="text-texto-tenue">{unidad}</span>
                    </span>
                  ),
                  efecto: (
                    <span className={dato && dato.coeficiente >= 0 ? 'text-alza' : 'text-baja'}>
                      {dato ? `${dato.coeficiente >= 0 ? '+' : ''}${fmt.decimal(dato.coeficiente)} MUSD` : '—'}
                    </span>
                  ),
                  intervalo: dato
                    ? `${fmt.decimal(dato.ic_95[0])} a ${fmt.decimal(dato.ic_95[1])}`
                    : '—',
                  p: dato ? fmt.pValor(dato.p_valor) : '—',
                };
              })}
            />
            <Nota>
              {sensibilidad.modelo_operativo.observaciones} trimestres (
              {sensibilidad.modelo_operativo.periodo.join(' a ')}). {sensibilidad.advertencia}
            </Nota>
          </Tarjeta>
        </div>
      </Seccion>

      {/* ------------------------------------------------------------------ */}
      <Seccion
        id="mercado"
        numero="03"
        titulo="El mercado no le creyó — y no es la primera vez"
        bajada={
          <>
            Para separar la reacción al balance del ruido del sector se estima, antes de cada
            reporte, un modelo de mercado contra Vista y el Brent sobre 120 ruedas. Lo que ese
            modelo no explica el día del balance es la reacción al balance.
          </>
        }
      >
        <div className="grid gap-3 sm:grid-cols-3">
          <Dato
            etiqueta="Balances con reacción negativa"
            valor={`${mercado.resumen.con_reaccion_negativa} de ${mercado.resumen.balances}`}
            detalle="retorno anormal por debajo de cero"
            tono="baja"
          />
          <Dato
            etiqueta="Reacción anormal mediana"
            valor={fmt.porcentajeConSigno(mercado.resumen.retorno_anormal_mediano, 2)}
            detalle="mediana de los 22 balances desde 2020"
          />
          <Dato
            etiqueta="100 pb de riesgo país"
            valor={fmt.porcentajeConSigno(mercado.riesgo_pais.efecto_100pb_riesgo_pais, 1)}
            detalle={`en el retorno diario, con Brent controlado (p ${fmt.pValor(mercado.riesgo_pais.efecto_100pb_p)})`}
            tono="baja"
          />
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <Tarjeta titulo="Retorno anormal el día de cada balance">
            <ReaccionBalances eventos={mercado.eventos} />
            <Nota>
              El día del evento no es la fecha de presentación que figura en EDGAR: un release
              aceptado a las 18:20 queda fechado al día siguiente, y usar esa fecha mide la rueda
              equivocada. Se usa la hora real de aceptación del filing.
            </Nota>
          </Tarjeta>

          <Tarjeta titulo="La acción contra sus comparables y el riesgo país (base 100 en 2021)">
            <AccionYRiesgoPais serie={mercado.serie_semanal} />
            <Nota>
              El área roja es el EMBI+ Argentina. La acción de YPF se mueve con el crudo y con Vista,
              pero además paga el descuento del país: es el canal que separa lo que es de la compañía
              de lo que es del lugar donde opera.
            </Nota>
          </Tarjeta>
        </div>
      </Seccion>

      {/* ------------------------------------------------------------------ */}
      <Seccion
        id="activo"
        numero="04"
        titulo="El activo, pozo por pozo"
        bajada={
          <>
            {fmt.entero(produccion.cobertura.pozos_vaca_muerta)} pozos de Vaca Muerta sobre{' '}
            {fmt.entero(produccion.cobertura.pozos)} no convencionales, con producción mensual
            declarada desde {produccion.cobertura.desde} hasta {produccion.cobertura.hasta}. El dato
            oficial es producción bruta operada: incluye la parte de los socios, así que es mayor que
            la que YPF consolida en el balance.
          </>
        }
      >
        <div className="grid gap-6 lg:grid-cols-2">
          <Tarjeta titulo="Producción de Vaca Muerta por operador">
            <ProduccionPorOperador puntos={produccion.vaca_muerta_por_operador} />
          </Tarjeta>
          <Tarjeta titulo="Curvas tipo por año de puesta en producción">
            <CurvasTipo curvas={declive.curva_tipo_por_vintage} />
            <Nota>
              Caudal mediano de petróleo por mes de producción, no promedio: un puñado de pozos
              excepcionales corre el promedio y deja de describir al pozo típico. Cada cohorte arranca
              más arriba que la anterior — la curva de aprendizaje de la cuenca es visible.
            </Nota>
          </Tarjeta>
        </div>

        <div className="mt-6">
          <MapaCuenca />
        </div>
      </Seccion>

      {/* ------------------------------------------------------------------ */}
      <Seccion
        id="economia"
        numero="05"
        titulo="Cuánto vale perforar un pozo"
        bajada={
          <>
            Se ajusta una curva de Arps a cada uno de los {fmt.entero(declive.pozos_ajustados)} pozos
            de petróleo con historia suficiente y se evalúa el flujo de fondos como si ese pozo se
            perforara hoy: capex US${' '}
            {fmt.entero((economia.supuestos.capex_usd as number) / 1e6)}M, opex US${' '}
            {economia.supuestos.opex_usd_bbl}/bbl, regalías{' '}
            {fmt.porcentaje(economia.supuestos.regalias as number, 0)} y WACC{' '}
            {fmt.porcentaje(economia.supuestos.wacc_anual as number, 0)}.
          </>
        }
      >
        <div className="grid gap-3 sm:grid-cols-4">
          <Dato
            etiqueta="NPV mediano por pozo"
            valor={`US$ ${fmt.decimal(economia.resumen.npv_musd_mediano)}M`}
            detalle={`${fmt.porcentaje(economia.resumen.pozos_con_npv_positivo, 0)} de los pozos con NPV positivo`}
            tono="crudo"
          />
          <Dato
            etiqueta="TIR mediana"
            valor={fmt.porcentaje(economia.resumen.irr_mediana, 0)}
            detalle={`payback ${fmt.entero(economia.resumen.payback_meses_mediano)} meses`}
          />
          <Dato
            etiqueta="Brent de breakeven"
            valor={`US$ ${fmt.decimal(economia.resumen.breakeven_brent_mediano)}`}
            detalle="mediano, por debajo del cual el pozo no repaga"
          />
          <Dato
            etiqueta="Prima de riesgo país"
            valor={`US$ ${fmt.decimal(economia.resumen.prima_riesgo_pais_musd_mediana)}M`}
            detalle="lo que pierde cada pozo por descontar al 12% y no al 10%"
            tono="baja"
          />
        </div>

        <div className="mt-6">
          <Tarjeta titulo="Economía del pozo tipo por operador">
            <Tabla
              columnas={[
                { clave: 'operador', titulo: 'Operador' },
                { clave: 'pozos', titulo: 'Pozos', alineacion: 'der' },
                { clave: 'npv', titulo: 'NPV mediano', alineacion: 'der' },
                { clave: 'tir', titulo: 'TIR', alineacion: 'der' },
                { clave: 'breakeven', titulo: 'Breakeven', alineacion: 'der' },
                { clave: 'eur', titulo: 'EUR mediana', alineacion: 'der' },
              ]}
              filas={economia.por_operador.slice(0, 6).map((fila) => ({
                operador: fila.operador,
                pozos: fmt.entero(fila.pozos),
                npv: (
                  <span className={fila.npv_musd_mediano >= 0 ? 'text-alza' : 'text-baja'}>
                    US$ {fmt.decimal(fila.npv_musd_mediano)}M
                  </span>
                ),
                tir: fmt.porcentaje(fila.irr_mediana, 0),
                breakeven: `US$ ${fmt.decimal(fila.breakeven_brent_mediano)}`,
                eur: `${fmt.entero(fila.eur_bbl_mediana / 1000)} Mbbl`,
              }))}
            />
            <Nota>
              {economia.advertencia} Vista aparece con el doble de NPV mediano que YPF y un breakeven
              diez dólares más bajo: opera menos pozos, pero más productivos y más nuevos.
            </Nota>
          </Tarjeta>
        </div>
      </Seccion>

      {/* ------------------------------------------------------------------ */}
      <Seccion
        id="simulador"
        numero="06"
        titulo="Simulador de escenarios"
        bajada={
          <>
            Los coeficientes del modelo, convertidos en una función pura que corre entera en el
            navegador. Mové un driver y el EBITDA proyectado se recalcula sin pedirle nada a ningún
            servidor.
          </>
        }
      >
        <Simulador />
      </Seccion>

      {/* ------------------------------------------------------------------ */}
      <Seccion
        id="metodo"
        numero="07"
        titulo="Cómo está hecho"
        bajada="Todo sale de fuentes públicas y de un pipeline que se puede volver a correr entero con un comando."
      >
        <div className="grid gap-6 md:grid-cols-2">
          <Tarjeta titulo="Fuentes">
            <ul className="space-y-2 text-sm text-texto-suave">
              <li>
                <span className="text-texto">SEC EDGAR</span> — 6-K y 20-F de YPF: la serie
                financiera trimestral sale de la tabla de highlights de cada earnings release.
              </li>
              <li>
                <span className="text-texto">Secretaría de Energía</span> — producción mensual por
                pozo, concesiones, cuencas y yacimientos.
              </li>
              <li>
                <span className="text-texto">Yahoo Finance</span> — YPF, Vista, Pampa, Brent, WTI y
                tipo de cambio.
              </li>
              <li>
                <span className="text-texto">EMBI+ Argentina</span> — riesgo país diario desde 1999.
              </li>
              <li>
                <span className="text-texto">IGN y Copernicus DEM</span> — límites por WFS y relieve
                de la cuenca.
              </li>
            </ul>
          </Tarjeta>

          <Tarjeta titulo="Advertencias que conviene leer antes de citar un número">
            <ul className="space-y-2 text-sm text-texto-suave">
              <li>
                La producción oficial es <span className="text-texto">bruta operada</span>: para el
                2T26 da 321 Kbbl/d de shale contra los {fmt.decimal(ultimo.shale_oil_kbbld)} Kbbl/d
                que reporta la compañía, porque incluye la participación de los socios.
              </li>
              <li>
                Las EUR salen de la curva ajustada a 30 años, no son reservas certificadas.
              </li>
              <li>
                Los coeficientes se estiman sobre {sensibilidad.modelo_operativo.observaciones}{' '}
                trimestres: el intervalo es parte del resultado.
              </li>
              <li>
                El NPV por pozo es greenfield y no incluye retenciones, abandono ni capital de
                trabajo.
              </li>
            </ul>
          </Tarjeta>
        </div>

        <div className="mt-8 rounded-lg border border-azul/50 bg-superficie p-6">
          <h3 className="text-lg font-semibold text-texto">Memo ejecutivo</h3>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-texto-suave">
            La conclusión del caso en una página, en formato de nota de equity research: qué pasó en
            el trimestre, por qué el precio no lo acompañó, qué tendría que ser cierto para
            revalorizar y qué riesgos tiene esa lectura.
          </p>
          <Link
            href="/ypf-project/memo"
            className="mt-4 inline-block rounded-md bg-azul px-4 py-2 text-sm font-medium text-white transition hover:bg-azul-claro"
          >
            Leer el memo ejecutivo →
          </Link>
        </div>

        <p className="mt-8 text-sm text-texto-tenue">
          Datos financieros actualizados al {fmt.trimestre(ultimo.trimestre)} · producción hasta{' '}
          {produccion.cobertura.hasta} · generado por el pipeline el{' '}
          {financieros.generado.slice(0, 10)}.
        </p>
        </Seccion>
      </main>
    </Shell>
  );
}
