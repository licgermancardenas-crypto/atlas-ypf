// Catálogo de capas del mapa y escalas de color.
//
// Está separado del componente porque es configuración, no comportamiento: qué
// archivo trae cada capa, cuánto pesa y cómo se pinta. Tocar el mapa para
// agregar una capa nueva debería ser tocar solo esta tabla.
//
// Los colores van como tripletas RGB y no como var(--color-*): deck.gl pinta en
// WebGL y no resuelve variables de CSS. Es la única duplicación de paleta que
// queda en el proyecto y existe por esa razón, no por descuido.

export type RGB = [number, number, number];

export const PALETA = {
  azul: [0, 84, 235] as RGB,
  azulClaro: [77, 144, 255] as RGB,
  celeste: [117, 170, 219] as RGB,
  oro: [240, 168, 48] as RGB,
  alza: [63, 185, 138] as RGB,
  baja: [226, 96, 63] as RGB,
  neutro: [95, 112, 153] as RGB,
  blanco: [238, 243, 255] as RGB,
};

export type IdCapa =
  | 'relieve'
  | 'cuenca'
  | 'provincias'
  | 'concesiones'
  | 'yacimientos'
  | 'pozos'
  | 'rutas'
  | 'ductos'
  | 'gasoductos'
  | 'refinerias'
  | 'terminales'
  | 'instalaciones'
  | 'pueblos'
  | 'rios'
  | 'ferrocarril';

export interface DefinicionCapa {
  id: IdCapa;
  etiqueta: string;
  grupo: 'Base' | 'Actividad' | 'Logística' | 'Territorio';
  archivo?: string;
  /** Peso aproximado en KB, para avisar antes de encender una capa cara. */
  peso?: number;
  color: RGB;
  ayuda: string;
}

export const CAPAS: DefinicionCapa[] = [
  {
    id: 'relieve',
    etiqueta: 'Relieve',
    grupo: 'Base',
    color: PALETA.neutro,
    ayuda: 'Sombreado del terreno derivado del Copernicus DEM a 30 m.',
  },
  {
    id: 'provincias',
    etiqueta: 'Provincias',
    grupo: 'Base',
    archivo: 'provinces.geojson',
    peso: 44,
    color: PALETA.neutro,
    ayuda: 'Límites del IGN.',
  },
  {
    id: 'cuenca',
    etiqueta: 'Cuenca Neuquina',
    grupo: 'Base',
    archivo: 'basin.geojson',
    peso: 17,
    color: PALETA.celeste,
    ayuda: 'Contorno de la cuenca según la Secretaría de Energía.',
  },
  {
    id: 'concesiones',
    etiqueta: 'Concesiones',
    grupo: 'Actividad',
    archivo: 'concessions.geojson',
    peso: 121,
    color: PALETA.azul,
    ayuda: 'Áreas de explotación, con la producción de sus pozos ya agregada.',
  },
  {
    id: 'yacimientos',
    etiqueta: 'Yacimientos',
    grupo: 'Actividad',
    archivo: 'fields.geojson',
    peso: 333,
    color: PALETA.azulClaro,
    ayuda: 'Subdivisión de las concesiones; más detalle, más polígonos.',
  },
  {
    id: 'pozos',
    etiqueta: 'Pozos',
    grupo: 'Actividad',
    archivo: 'wells.geojson',
    peso: 1787,
    color: PALETA.oro,
    ayuda: '4.893 pozos no convencionales con producción acumulada, EUR y NPV.',
  },
  {
    id: 'ductos',
    etiqueta: 'Oleoductos y gasoductos',
    grupo: 'Logística',
    archivo: 'pipelines.geojson',
    peso: 1946,
    color: PALETA.oro,
    ayuda: 'Ductos de la Res. 319/93, sin los acueductos de inyección.',
  },
  {
    id: 'gasoductos',
    etiqueta: 'Gasoductos troncales',
    grupo: 'Logística',
    archivo: 'gas_pipelines.geojson',
    peso: 28,
    color: PALETA.celeste,
    ayuda: 'Red de transporte de ENARGAS: por dónde sale el gas de la cuenca.',
  },
  {
    id: 'refinerias',
    etiqueta: 'Refinerías',
    grupo: 'Logística',
    archivo: 'refineries.geojson',
    peso: 3,
    color: PALETA.baja,
    ayuda: 'Las 15 refinerías del país, el destino del crudo.',
  },
  {
    id: 'terminales',
    etiqueta: 'Terminales de despacho',
    grupo: 'Logística',
    archivo: 'terminals.geojson',
    peso: 6,
    color: PALETA.alza,
    ayuda: 'Terminales de combustibles líquidos.',
  },
  {
    id: 'instalaciones',
    etiqueta: 'Plantas e instalaciones',
    grupo: 'Logística',
    archivo: 'facilities.geojson',
    peso: 188,
    color: PALETA.azulClaro,
    ayuda: 'Baterías, plantas de tratamiento y acopio empadronadas (Res. 318).',
  },
  {
    id: 'rutas',
    etiqueta: 'Rutas',
    grupo: 'Territorio',
    archivo: 'roads.geojson',
    peso: 206,
    color: PALETA.neutro,
    ayuda: 'Red vial nacional y provincial del IGN.',
  },
  {
    id: 'pueblos',
    etiqueta: 'Localidades',
    grupo: 'Territorio',
    archivo: 'towns.geojson',
    peso: 23,
    color: PALETA.blanco,
    ayuda: 'Ciudades y pueblos: la mano de obra y los servicios salen de acá.',
  },
  {
    id: 'ferrocarril',
    etiqueta: 'Ferrocarril',
    grupo: 'Logística',
    archivo: 'rail.geojson',
    peso: 7,
    color: PALETA.celeste,
    ayuda: 'La traza por la que entra la arena de fractura.',
  },
  {
    id: 'rios',
    etiqueta: 'Ríos',
    grupo: 'Territorio',
    archivo: 'rivers.geojson',
    peso: 898,
    color: PALETA.celeste,
    ayuda: 'Cursos permanentes: el agua de fractura sale de ahí.',
  },
];

// Lo que se ve al abrir: suficiente para leer el mapa sin bajar ocho megas.
export const CAPAS_INICIALES: IdCapa[] = [
  'relieve',
  'cuenca',
  'concesiones',
  'pozos',
  'rutas',
  'pueblos',
];

// --------------------------------------------------------------------------- //
// Coroplético
// --------------------------------------------------------------------------- //
export type IdVariable = 'boe_acum_mboe' | 'pozos' | 'npv_musd_mediano' | 'boe_por_pozo_mboe';

export interface Variable {
  id: IdVariable;
  etiqueta: string;
  unidad: string;
  /** Divergente: el cero significa algo (repaga o no repaga el capex). */
  divergente?: boolean;
  ayuda: string;
}

export const VARIABLES: Variable[] = [
  {
    id: 'boe_acum_mboe',
    etiqueta: 'Producción acumulada',
    unidad: 'Mboe',
    ayuda: 'Todo lo que salió del área desde el primer pozo.',
  },
  {
    id: 'pozos',
    etiqueta: 'Pozos perforados',
    unidad: 'pozos',
    ayuda: 'Cuántos pozos no convencionales tiene el área.',
  },
  {
    id: 'boe_por_pozo_mboe',
    etiqueta: 'Producción por pozo',
    unidad: 'Mboe/pozo',
    ayuda: 'Productividad: hace comparable un área chica con una enorme.',
  },
  {
    id: 'npv_musd_mediano',
    etiqueta: 'NPV mediano por pozo',
    unidad: 'US$ M',
    divergente: true,
    ayuda: 'Valor del pozo típico del área si se perforara hoy. El cero divide.',
  },
];

// Rampa secuencial sobre el azul de YPF: de casi el fondo al azul de marca
// encendido. La marca ya define el color; la escala solo define la intensidad.
const RAMPA_SECUENCIAL: RGB[] = [
  [14, 30, 66],
  [18, 52, 120],
  [10, 74, 180],
  [0, 84, 235],
  [77, 144, 255],
];

// Rampa divergente para el NPV: rojo el pozo que no repaga el capex de hoy,
// verde el que sí. Son dos preguntas distintas y por eso son dos escalas.
const RAMPA_DIVERGENTE: RGB[] = [
  [178, 58, 38],
  [226, 96, 63],
  [95, 112, 153],
  [63, 185, 138],
  [34, 148, 106],
];

/** Cuantiles de los valores presentes, que es lo que evita que un área gigante
 *  se coma toda la escala y deje al resto en el mismo tono. */
export function cortes(valores: number[], n = 5): number[] {
  const limpios = valores.filter((v) => Number.isFinite(v)).sort((a, b) => a - b);
  if (!limpios.length) return [];
  return Array.from({ length: n - 1 }, (_, i) =>
    limpios[Math.floor(((i + 1) / n) * (limpios.length - 1))],
  );
}

export function colorEscala(valor: number | null, quiebres: number[], divergente: boolean): RGB {
  if (valor === null || !Number.isFinite(valor)) return [26, 38, 66];
  const rampa = divergente ? RAMPA_DIVERGENTE : RAMPA_SECUENCIAL;
  let indice = 0;
  while (indice < quiebres.length && valor > quiebres[indice]) indice += 1;
  return rampa[Math.min(indice, rampa.length - 1)];
}

export { RAMPA_SECUENCIAL, RAMPA_DIVERGENTE };
