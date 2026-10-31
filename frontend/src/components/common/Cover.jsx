import { useState } from 'react';
import { coverGrad, initials } from '../../utils/trendFormat';
import './Cover.css';

export default function Cover({ item, className })
{
  const [failedUrl, setFailedUrl] = useState(null);
  const showImage = Boolean(item.cover) && item.cover !== failedUrl;

  return (
    <div className={`cover ${className}`} style={{ background: coverGrad(item.key) }}>
      {initials(item.title)}
      {showImage && (
        <img
          className="cover-img"
          src={item.cover}
          alt=""
          loading="lazy"
          referrerPolicy="no-referrer"
          onError={() => setFailedUrl(item.cover)}
        />
      )}
    </div>
  );
}
