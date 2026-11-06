import { useState } from 'react';
import { coverGrad, initials } from '../../utils/trendFormat';
import './Cover.css';

function shapeOf(image)
{
  const ratio = image.naturalWidth / image.naturalHeight;

  if (ratio < 0.9)
  {
    return 'tall';
  }

  if (ratio > 1.1)
  {
    return 'wide';
  }

  return 'square';
}

export default function Cover({ item, className, adaptive = false, squareCrop = false})
{
  const [failedUrl, setFailedUrl] = useState(null);
  const [shape, setShape] = useState({ url: null, value: 'square' });
  const showImage = Boolean(item.cover) && item.cover !== failedUrl;
  const shapeClass = adaptive && shape.url === item.cover ? ` cover--${shape.value}` : '';

  const handleLoad = (event) =>
  {
    if (adaptive)
    {
      setShape({ url: item.cover, value: shapeOf(event.currentTarget) });
    }
  };

  return (
    <div className={`cover ${className}${shapeClass}${squareCrop ? ' cover--movie' : ''}`} style={{ background: coverGrad(item.key) }}>
      {initials(item.title)}
      {showImage && (
        <img
          className="cover-img"
          src={item.cover}
          alt=""
          loading="lazy"
          referrerPolicy="no-referrer"
          onLoad={handleLoad}
          onError={() => setFailedUrl(item.cover)}
        />
      )}
    </div>
  );
}