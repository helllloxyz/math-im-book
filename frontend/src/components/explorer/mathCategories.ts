export interface MathCategory {
  id: string;
  label: string;
  description: string;
  iconUrl: string;
}

const iconUrl = (fileName: string) =>
  new URL(`../../assets/math-category-icons/${fileName}.svg`, import.meta.url).href;

export const MATH_CATEGORIES: readonly MathCategory[] = [
  {
    id: 'algebra',
    label: 'Algebra',
    description: 'Equations, polynomials, and symbolic structures',
    iconUrl: iconUrl('algebra'),
  },
  {
    id: 'geometry',
    label: 'Geometry',
    description: 'Shapes, spaces, and geometric constructions',
    iconUrl: iconUrl('geometry'),
  },
  {
    id: 'linear-algebra',
    label: 'Linear algebra',
    description: 'Vectors, matrices, and linear maps',
    iconUrl: iconUrl('linear-algebra'),
  },
  {
    id: 'calculus-analysis',
    label: 'Calculus & analysis',
    description: 'Limits, derivatives, integrals, and series',
    iconUrl: iconUrl('calculus-analysis'),
  },
  {
    id: 'group-theory',
    label: 'Groups & symmetry',
    description: 'Groups, representations, and abstract symmetry',
    iconUrl: iconUrl('group-theory'),
  },
  {
    id: 'number-theory',
    label: 'Number theory',
    description: 'Primes, integers, and arithmetic structure',
    iconUrl: iconUrl('number-theory'),
  },
  {
    id: 'probability-statistics',
    label: 'Probability & stats',
    description: 'Randomness, distributions, and inference',
    iconUrl: iconUrl('probability-statistics'),
  },
  {
    id: 'discrete-combinatorics',
    label: 'Discrete & combinatorics',
    description: 'Graphs, counting, and discrete structures',
    iconUrl: iconUrl('discrete-combinatorics'),
  },
  {
    id: 'logic-foundations',
    label: 'Logic & foundations',
    description: 'Logic, sets, categories, and foundations',
    iconUrl: iconUrl('logic-foundations'),
  },
  {
    id: 'topology',
    label: 'Topology',
    description: 'Continuity, manifolds, knots, and spaces',
    iconUrl: iconUrl('topology'),
  },
  {
    id: 'applied-modeling',
    label: 'Applied & modeling',
    description: 'Differential equations, optimization, and models',
    iconUrl: iconUrl('applied-modeling'),
  },
  {
    id: 'general',
    label: 'General mathematics',
    description: 'Mixed, elementary, or cross-category topics',
    iconUrl: iconUrl('general'),
  },
] as const;

const categoryMap = new Map(MATH_CATEGORIES.map((category) => [category.id, category]));

const legacyCategoryMap: Record<string, string> = {
  function: 'calculus-analysis',
  sigma: 'discrete-combinatorics',
  matrix: 'linear-algebra',
  triangle: 'geometry',
  atom: 'general',
  wave: 'applied-modeling',
  orbit: 'group-theory',
};

export const mathCategoryFor = (id?: string | null): MathCategory => {
  const normalizedId = legacyCategoryMap[id || ''] || id || 'general';
  return categoryMap.get(normalizedId) || categoryMap.get('general')!;
};
