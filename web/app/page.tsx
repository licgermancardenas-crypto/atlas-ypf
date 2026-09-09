import { redirect } from 'next/navigation';

// Esta app existe para servir el caso; la raíz solo lleva a la ruta que después
// se integra al portfolio.
export default function Home() {
  redirect('/ypf-project');
}
