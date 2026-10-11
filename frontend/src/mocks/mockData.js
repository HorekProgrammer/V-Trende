export const CATEGORIES = 
[
  { id: 'music', label: 'Музыка', genres: ['Поп', 'Рэп / Хип-хоп', 'Рок', 'Электроника', 'Инди'] },
  { id: 'movies', label: 'Фильмы', genres: ['Драма', 'Боевик', 'Триллер', 'Комедия', 'Фантастика'] },
  { id: 'games', label: 'Игры', genres: ['Экшен', 'RPG', 'Стратегии', 'Шутеры', 'Инди'] },
  { id: 'streamers', label: 'Стримеры', genres: ['Игры', 'Just Chatting', 'Музыка', 'IRL', 'Творчество'] },
];


export const TRENDS = 
[
  {
    key: 'music-1', sphere: 'music', categoryLabel: 'Музыка',
    rank: 1, prevRank: 2, peak: 1, weeks: 12,
    title: 'Стеклянный дождь', subtitle: 'Луна Реверс', genre: 'Поп',
    views: 1418000,
    history: [35, 25, 36, 37, 55, 60, 67, 70, 70, 72, 90, 90],
  },
  {
    key: 'music-2', sphere: 'music', categoryLabel: 'Музыка',
    rank: 2, prevRank: 1, peak: 1, weeks: 5,
    title: 'На созвоне', subtitle: 'Артём Куб', genre: 'Рэп / Хип-хоп',
    views: 780000,
    history: [4, 5, 5, 9, 6, 8, 8, 30, 39, 69, 70, 87],
  },
  {
    key: 'music-3', sphere: 'music', categoryLabel: 'Музыка',
    rank: 3, prevRank: 3, peak: 3, weeks: 3,
    title: 'Пепел и мёд', subtitle: 'ЙОКО', genre: 'Инди',
    views: 555000,
    history: [12, 6, 9, 11, 5, 4, 11, 8, 12, 36, 53, 74],
  },
  {
    key: 'music-4', sphere: 'music', categoryLabel: 'Музыка',
    rank: 4, prevRank: 6, peak: 2, weeks: 24,
    title: 'Город спит', subtitle: 'Марсель Дым', genre: 'Рэп / Хип-хоп',
    views: 439000,
    history: [24, 22, 34, 41, 34, 36, 40, 42, 58, 66, 62, 66],
  },
  {
    key: 'music-5', sphere: 'music', categoryLabel: 'Музыка',
    rank: 5, prevRank: 4, peak: 4, weeks: 2,
    title: 'Невесомость', subtitle: 'DIVA NOVA', genre: 'Электроника',
    views: 368000,
    history: [8, 9, 12, 4, 11, 7, 4, 6, 5, 9, 46, 61],
  },
  {
    key: 'music-6', sphere: 'music', categoryLabel: 'Музыка',
    rank: 6, prevRank: 5, peak: 1, weeks: 31,
    title: 'Полночный поезд', subtitle: 'Сергей Атлас', genre: 'Рок',
    views: 320000,
    history: [32, 19, 35, 31, 27, 28, 35, 52, 52, 51, 53, 55],
  },
  {
    key: 'music-7', sphere: 'music', categoryLabel: 'Музыка',
    rank: 7, prevRank: 9, peak: 7, weeks: 1,
    title: 'Осколки неона', subtitle: 'RINA', genre: 'Электроника',
    views: 239000,
    history: [6, 10, 4, 5, 12, 5, 9, 4, 12, 7, 4, 43],
  },
  {
    key: 'music-8', sphere: 'music', categoryLabel: 'Музыка',
    rank: 8, prevRank: 7, peak: 3, weeks: 18,
    title: 'Тихий океан', subtitle: 'Гриша Свет', genre: 'Инди',
    views: 218000,
    history: [23, 25, 18, 22, 18, 20, 23, 27, 38, 29, 36, 34],
  },
  {
    key: 'movies-1', sphere: 'movies', categoryLabel: 'Фильмы',
    rank: 1, prevRank: 1, peak: 1, weeks: 9,
    title: 'Стеклянный горизонт', subtitle: 'реж. И. Ветров', genre: 'Фантастика',
    views: 1455000,
    history: [9, 8, 6, 24, 27, 45, 59, 65, 61, 77, 92, 92],
  },
  {
    key: 'movies-2', sphere: 'movies', categoryLabel: 'Фильмы',
    rank: 2, prevRank: 4, peak: 2, weeks: 4,
    title: 'Тень Полярной звезды', subtitle: 'реж. О. Марин', genre: 'Триллер',
    views: 800000,
    history: [4, 10, 11, 4, 7, 11, 11, 8, 32, 44, 76, 85],
  },
  {
    key: 'movies-3', sphere: 'movies', categoryLabel: 'Фильмы',
    rank: 3, prevRank: 2, peak: 2, weeks: 14,
    title: 'Дом на границе миров', subtitle: 'реж. Т. Рудь', genre: 'Драма',
    views: 569000,
    history: [33, 34, 39, 46, 52, 45, 49, 64, 68, 63, 65, 76],
  },
  {
    key: 'movies-4', sphere: 'movies', categoryLabel: 'Фильмы',
    rank: 4, prevRank: 3, peak: 1, weeks: 27,
    title: 'Последний рейс «Аврора»', subtitle: 'реж. Н. Соль', genre: 'Боевик',
    views: 450000,
    history: [23, 35, 34, 31, 43, 35, 50, 58, 55, 65, 62, 68],
  },
  {
    key: 'movies-5', sphere: 'movies', categoryLabel: 'Фильмы',
    rank: 5, prevRank: 6, peak: 5, weeks: 2,
    title: 'Комната 407', subtitle: 'реж. Е. Кадр', genre: 'Триллер',
    views: 377000,
    history: [8, 6, 7, 6, 7, 6, 6, 5, 12, 7, 40, 59],
  },
  {
    key: 'movies-6', sphere: 'movies', categoryLabel: 'Фильмы',
    rank: 6, prevRank: 5, peak: 3, weeks: 8,
    title: 'Полёт над бездной', subtitle: 'реж. Д. Рябов', genre: 'Боевик',
    views: 275000,
    history: [12, 7, 8, 8, 24, 20, 36, 34, 43, 45, 48, 49],
  },
  {
    key: 'movies-7', sphere: 'movies', categoryLabel: 'Фильмы',
    rank: 7, prevRank: 8, peak: 7, weeks: 1,
    title: 'Механическое сердце', subtitle: 'реж. С. Литвин', genre: 'Фантастика',
    views: 246000,
    history: [4, 12, 4, 6, 7, 4, 4, 6, 9, 7, 5, 42],
  },
  {
    key: 'movies-8', sphere: 'movies', categoryLabel: 'Фильмы',
    rank: 8, prevRank: 7, peak: 4, weeks: 22,
    title: 'Ночная смена', subtitle: 'реж. А. Грин', genre: 'Комедия',
    views: 224000,
    history: [27, 28, 24, 29, 24, 32, 20, 34, 30, 30, 32, 35],
  },
  {
    key: 'games-1', sphere: 'games', categoryLabel: 'Игры',
    rank: 1, prevRank: 3, peak: 1, weeks: 16,
    title: 'Astra Frontier', subtitle: 'Nordwind Studio', genre: 'Экшен',
    views: 1492000,
    history: [30, 32, 40, 44, 46, 64, 62, 63, 66, 79, 90, 93],
  },
  {
    key: 'games-2', sphere: 'games', categoryLabel: 'Игры',
    rank: 2, prevRank: 2, peak: 2, weeks: 7,
    title: 'Пепельные Хроники', subtitle: 'Кузница Игр', genre: 'RPG',
    views: 820000,
    history: [5, 11, 9, 7, 7, 35, 44, 43, 61, 64, 78, 82],
  },
  {
    key: 'games-3', sphere: 'games', categoryLabel: 'Игры',
    rank: 3, prevRank: 5, peak: 3, weeks: 2,
    title: 'Nightcode: Восстание', subtitle: 'Deep Pixel', genre: 'Шутеры',
    views: 583000,
    history: [4, 12, 5, 12, 7, 10, 9, 12, 8, 6, 48, 78],
  },
  {
    key: 'games-4', sphere: 'games', categoryLabel: 'Игры',
    rank: 4, prevRank: 4, peak: 1, weeks: 35,
    title: 'Кузница Богов', subtitle: 'Anvil Team', genre: 'Стратегии',
    views: 461000,
    history: [19, 27, 26, 38, 50, 41, 40, 57, 62, 55, 60, 70],
  },
  {
    key: 'games-5', sphere: 'games', categoryLabel: 'Игры',
    rank: 5, prevRank: 6, peak: 4, weeks: 11,
    title: 'Дрифт Империя', subtitle: 'Redline Dev', genre: 'Экшен',
    views: 324000,
    history: [10, 27, 27, 36, 31, 43, 48, 40, 55, 58, 53, 58],
  },
  {
    key: 'games-6', sphere: 'games', categoryLabel: 'Игры',
    rank: 6, prevRank: 9, peak: 6, weeks: 1,
    title: 'Забытый Маяк', subtitle: 'Lonely Coast', genre: 'Инди',
    views: 283000,
    history: [7, 4, 11, 6, 5, 9, 5, 7, 8, 4, 9, 50],
  },
  {
    key: 'games-7', sphere: 'games', categoryLabel: 'Игры',
    rank: 7, prevRank: 7, peak: 3, weeks: 19,
    title: 'Cyber Vendetta', subtitle: 'Glitchworks', genre: 'Шутеры',
    views: 253000,
    history: [22, 18, 18, 38, 31, 38, 39, 45, 42, 38, 42, 47],
  },
  {
    key: 'games-8', sphere: 'games', categoryLabel: 'Игры',
    rank: 8, prevRank: 8, peak: 2, weeks: 28,
    title: 'Королевство Теней', subtitle: 'Umbra Games', genre: 'RPG',
    views: 230000,
    history: [24, 32, 20, 23, 24, 26, 26, 25, 28, 35, 28, 38],
  },
  {
    key: 'streamers-1', sphere: 'streamers', categoryLabel: 'Стримеры',
    rank: 1, prevRank: 1, peak: 1, weeks: 11,
    title: 'GrimTactic', subtitle: 'Игры · FPS', genre: 'Игры',
    views: 1530000,
    history: [4, 24, 33, 46, 38, 52, 51, 66, 81, 83, 79, 92],
  },
  {
    key: 'streamers-2', sphere: 'streamers', categoryLabel: 'Стримеры',
    rank: 2, prevRank: 3, peak: 2, weeks: 6,
    title: 'NovaPlay', subtitle: 'Just Chatting', genre: 'Just Chatting',
    views: 840000,
    history: [7, 7, 10, 12, 4, 6, 37, 34, 60, 60, 79, 86],
  },
  {
    key: 'streamers-3', sphere: 'streamers', categoryLabel: 'Стримеры',
    rank: 3, prevRank: 2, peak: 2, weeks: 3,
    title: 'КиберЛиса', subtitle: 'Игры · RPG', genre: 'Игры',
    views: 597000,
    history: [11, 8, 8, 7, 5, 5, 8, 12, 9, 38, 61, 78],
  },
  {
    key: 'streamers-4', sphere: 'streamers', categoryLabel: 'Стримеры',
    rank: 4, prevRank: 4, peak: 1, weeks: 26,
    title: 'ТихийШторм', subtitle: 'Музыка', genre: 'Музыка',
    views: 396000,
    history: [19, 36, 27, 33, 34, 48, 50, 47, 51, 52, 64, 65],
  },
  {
    key: 'streamers-5', sphere: 'streamers', categoryLabel: 'Стримеры',
    rank: 5, prevRank: 7, peak: 5, weeks: 2,
    title: 'PixelJam', subtitle: 'Инди-разработка', genre: 'Творчество',
    views: 333000,
    history: [5, 9, 8, 5, 12, 9, 10, 10, 4, 4, 34, 61],
  },
  {
    key: 'streamers-6', sphere: 'streamers', categoryLabel: 'Стримеры',
    rank: 6, prevRank: 5, peak: 3, weeks: 15,
    title: 'Атмосфера_', subtitle: 'IRL', genre: 'IRL',
    views: 290000,
    history: [23, 16, 25, 30, 26, 40, 42, 37, 38, 52, 41, 53],
  },
  {
    key: 'streamers-7', sphere: 'streamers', categoryLabel: 'Стримеры',
    rank: 7, prevRank: 6, peak: 6, weeks: 1,
    title: 'DarkSensei', subtitle: 'Файтинги', genre: 'Игры',
    views: 259000,
    history: [11, 5, 10, 6, 4, 6, 5, 12, 7, 6, 6, 41],
  },
  {
    key: 'streamers-8', sphere: 'streamers', categoryLabel: 'Стримеры',
    rank: 8, prevRank: 8, peak: 4, weeks: 21,
    title: 'МаякStream', subtitle: 'Творчество', genre: 'Творчество',
    views: 235000,
    history: [18, 17, 23, 22, 31, 18, 20, 23, 31, 38, 33, 33],
  },
];


export function getTrendsByCategory(categoryId)
{
  return TRENDS.filter((t) => t.sphere === categoryId).sort((a, b) => a.rank - b.rank);
}

export function getTrendById(key) 
{
  return TRENDS.find((t) => t.key === key);
}

export function getGlobalTrends(limit = 10) 
{
  return [...TRENDS].sort((a, b) => b.views - a.views).slice(0, limit);
}

export function getNewTrends(limit = 10) 
{
  return [...TRENDS].sort((a, b) => a.weeks - b.weeks).slice(0, limit);
}

export function getLegendaryTrends(limit = 10) 
{
  return [...TRENDS].sort((a, b) => b.weeks - a.weeks).slice(0, limit);
}

export function getTop3ByCategory() 
{
  return CATEGORIES.map((category) => 
    ({
    category,
    items: getTrendsByCategory(category.id).slice(0, 3),
  }));
}