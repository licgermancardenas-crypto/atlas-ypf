// La lectura principal: qué está pasando, en dos frases.
//
// Es lo primero que se lee después del título y existe porque un número solo no
// es una lectura. "564 kboe/d" no dice nada sin saber si eso sube o baja, qué
// lo mueve y cuál es el activo que lo explica.
//
// Lo importante: la frase se arma con los mismos arrays que dibujan el gráfico
// (ver lib/produccion.ts). No hay texto editorial escondido acá: si el próximo
// refresco del pipeline da otra cosa, esto dice otra cosa. Cuando el dato no
// alcanza para afirmar algo, la función devuelve null y el bloque no aparece,
// que es preferible a un titular que no se puede sostener.

import { lectura, type ProduccionYPF } from '@/lib/produccion';

export function SenalEjecutiva({ datos }: { datos: ProduccionYPF }) {
  const señal = lectura(datos);
  if (!señal) return null;

  return (
    <section
      aria-labelledby="lectura-principal"
      className="relative overflow-hidden rounded-lg border border-borde bg-superficie/60 py-5 pl-6 pr-5"
    >
      {/* La barra de la izquierda es la misma marca que usa el resto del sitio
          para decir "esto es una conclusión, no un dato más". */}
      <span
        aria-hidden
        className="absolute inset-y-0 left-0 w-[3px] bg-gradient-to-b from-azul via-azul-claro to-oro"
      />
      <h2
        id="lectura-principal"
        className="font-mono text-[0.68rem] uppercase tracking-[0.16em] text-texto-tenue"
      >
        Lectura principal
      </h2>
      <p className="mt-2.5 max-w-4xl text-base leading-relaxed text-texto sm:text-lg">
        {señal.titulo}
      </p>
      {señal.cuerpo ? (
        <p className="mt-2 max-w-4xl text-sm leading-relaxed text-texto-suave">{señal.cuerpo}</p>
      ) : null}
      <p className="mt-3 font-mono text-[0.66rem] uppercase tracking-[0.12em] text-texto-tenue">
        Calculado sobre los últimos doce meses contra los doce previos · fuente: {datos.fuente}
      </p>
    </section>
  );
}
