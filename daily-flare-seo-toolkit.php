<?php
/**
 * Plugin Name: Daily Flare SEO Toolkit
 * Description: Native WordPress SEO auditing, reporting and safe diagnostics for The Daily Flare. Read-only by design.
 * Version: 1.0.0
 * Author: The Daily Flare
 * License: GPL-2.0-or-later
 * Requires at least: 6.2
 * Requires PHP: 7.4
 */
if (!defined('ABSPATH')) exit;

final class Daily_Flare_SEO_Toolkit {
    const VERSION = '1.0.0';
    const OPTION = 'df_seo_toolkit_report';
    const MENU = 'daily-flare-seo';

    public static function init() {
        add_action('admin_menu', [__CLASS__, 'admin_menu']);
        add_action('admin_post_df_run_audit', [__CLASS__, 'run_audit_action']);
        add_action('rest_api_init', [__CLASS__, 'rest_routes']);
        add_action('init', [__CLASS__, 'register_nibwp_abilities'], 20);
    }

    public static function admin_menu() {
        add_menu_page('Daily Flare SEO', 'Daily Flare SEO', 'manage_options', self::MENU, [__CLASS__, 'dashboard'], 'dashicons-chart-area', 58);
        add_submenu_page(self::MENU, 'Dashboard', 'Dashboard', 'manage_options', self::MENU, [__CLASS__, 'dashboard']);
        add_submenu_page(self::MENU, 'Findings', 'Findings', 'manage_options', 'daily-flare-seo-findings', [__CLASS__, 'findings_page']);
        add_submenu_page(self::MENU, 'Settings', 'Settings', 'manage_options', 'daily-flare-seo-settings', [__CLASS__, 'settings_page']);
    }

    private static function base_url() { return untrailingslashit(home_url('/')); }

    private static function request($url) {
        $r = wp_remote_get($url, ['timeout'=>15, 'redirection'=>5, 'user-agent'=>'DailyFlareSEOToolkit/'.self::VERSION.' (+'.self::base_url().')']);
        if (is_wp_error($r)) return ['error'=>$r->get_error_message(), 'status'=>0, 'final_url'=>$url, 'headers'=>[]];
        $headers = wp_remote_retrieve_headers($r);
        return ['status'=>(int)wp_remote_retrieve_response_code($r), 'final_url'=>wp_remote_retrieve_header($r,'location') ?: $url, 'content_type'=>wp_remote_retrieve_header($r,'content-type'), 'x_robots_tag'=>wp_remote_retrieve_header($r,'x-robots-tag'), 'body'=>wp_remote_retrieve_body($r), 'headers'=>$headers];
    }

    private static function urls_from_sitemap() {
        $candidates = [self::base_url().'/sitemap.xml', self::base_url().'/wp-sitemap.xml', self::base_url().'/sitemap_index.xml'];
        $urls = [];
        foreach ($candidates as $candidate) {
            $r = self::request($candidate);
            if ($r['status'] !== 200 || stripos((string)$r['content_type'], 'xml') === false) continue;
            preg_match_all('/<loc>\s*([^<]+)\s*<\/loc>/i', $r['body'], $m);
            foreach ($m[1] as $loc) {
                $loc = html_entity_decode(trim($loc));
                if (substr(strtolower($loc), -4) === '.xml') {
                    $sr = self::request($loc);
                    if ($sr['status'] === 200) {
                        preg_match_all('/<loc>\s*([^<]+)\s*<\/loc>/i', $sr['body'], $sm);
                        foreach ($sm[1] as $u) $urls[] = html_entity_decode(trim($u));
                    }
                } else $urls[] = $loc;
            }
            if ($urls) break;
        }
        return array_values(array_unique(array_filter($urls, function($u){ return strpos($u, self::base_url()) === 0; })));
    }

    private static function audit_page($url) {
        $r = self::request($url);
        $out = ['url'=>$url,'status'=>$r['status'],'final_url'=>$r['final_url'],'issues'=>[],'internal_links'=>[],'images'=>[]];
        if ($r['status'] !== 200 || stripos((string)$r['content_type'], 'html') === false) { $out['issues'][]='page-not-html-or-not-200'; return $out; }
        libxml_use_internal_errors(true);
        $dom = new DOMDocument(); @$dom->loadHTML('<?xml encoding="UTF-8">'.$r['body']);
        $xp = new DOMXPath($dom);
        $title = trim($xp->evaluate('string(//title)'));
        $desc = trim($xp->evaluate('string(//meta[translate(@name,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz")="description"]/@content)'));
        $canonical = trim($xp->evaluate('string(//link[contains(concat(" ",normalize-space(@rel)," ")," canonical ")]/@href)'));
        $robots = trim($xp->evaluate('string(//meta[translate(@name,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz")="robots"]/@content)'));
        $h1nodes = $xp->query('//h1'); $h1s=[]; foreach($h1nodes as $h) $h1s[]=trim(preg_replace('/\s+/',' ',$h->textContent));
        $out += ['title'=>$title,'title_length'=>strlen($title),'meta_description'=>$desc,'meta_description_length'=>strlen($desc),'canonical'=>$canonical ? esc_url_raw($canonical) : null,'robots'=>$robots ?: null,'h1_count'=>count($h1s),'h1s'=>array_slice($h1s,0,5)];
        if (!$title) $out['issues'][]='missing-title'; elseif (strlen($title)<30 || strlen($title)>65) $out['issues'][]='title-length';
        if (!$desc) $out['issues'][]='missing-meta-description'; elseif (strlen($desc)<70 || strlen($desc)>165) $out['issues'][]='meta-description-length';
        if (!$canonical) $out['issues'][]='missing-canonical';
        if (count($h1s)===0) $out['issues'][]='missing-h1'; elseif(count($h1s)>1) $out['issues'][]='multiple-h1';
        if (stripos($robots,'noindex')!==false) $out['issues'][]='noindex';
        $imgs=$xp->query('//img'); foreach($imgs as $img){
            $src=trim($img->getAttribute('src')); if(!$src) $src=trim($img->getAttribute('data-src')); $full=$src?esc_url_raw(wp_http_validate_url($src)?$src:wp_make_link_relative($src)):'';
            if($src && strpos($src,'http')!==0) $full=esc_url_raw(self::base_url().'/'.ltrim($src,'/'));
            $alt=$img->hasAttribute('alt')?$img->getAttribute('alt'):null; $path=parse_url($full,PHP_URL_PATH)?:''; $name=pathinfo($path,PATHINFO_FILENAME);
            $generated=(bool)preg_match('/^(file[_-]?[a-z0-9]{6,}|(image|img|photo|picture)[_-]?[0-9a-z]{5,}|wp[_-]?[0-9]{5,}|dsc[_-]?[0-9]{4,}|pxl[_-]?[0-9]{4,}|[0-9]{5,}|[a-f0-9]{16,})$/i',$name);
            $issue=null; if($alt===null)$issue='missing-alt'; elseif(trim($alt)==='')$issue='empty-alt';
            $out['images'][]=['src'=>$full,'alt'=>$alt,'filename'=>$name,'issue'=>$issue,'filename_issue'=>$generated?'generated-or-generic-filename':null];
        }
        foreach($xp->query('//a[@href]') as $a){$href=trim($a->getAttribute('href')); if(!$href||$href[0]==='#')continue; $target=esc_url_raw($href); if(strpos($target,'http')!==0)$target=esc_url_raw(self::base_url().'/'.ltrim($target,'/')); if(parse_url($target,PHP_URL_HOST)===parse_url(self::base_url(),PHP_URL_HOST))$out['internal_links'][]=untrailingslashit($target);}
        $out['internal_links']=array_values(array_unique($out['internal_links'])); $out['internal_link_count']=count($out['internal_links']); if(!$out['internal_links'])$out['issues'][]='no-internal-links';
        $out['image_issues']=count(array_filter($out['images'],function($i){return !empty($i['issue'])||!empty($i['filename_issue']);}));
        return $out;
    }

    public static function run_audit($limit=50) {
        $limit=max(1,min(200,(int)$limit)); $urls=self::urls_from_sitemap();
        if(!$urls){ $q=new WP_Query(['post_type'=>['post','page'],'post_status'=>'publish','posts_per_page'=>$limit,'fields'=>'ids']); foreach($q->posts as $id)$urls[]=get_permalink($id); }
        $urls=array_slice(array_values(array_unique($urls)),0,$limit); if(!$urls)$urls=[self::base_url()];
        $pages=[]; foreach($urls as $u)$pages[]=self::audit_page($u);
        $title_groups=[];$desc_groups=[];$incoming=[];$audited=[]; foreach($pages as $p){$audited[$p['url']]=true;if(!empty($p['title']))$title_groups[strtolower(trim($p['title']))][]=$p['url'];if(!empty($p['meta_description']))$desc_groups[strtolower(trim($p['meta_description']))][]=$p['url'];foreach($p['internal_links'] as $l)if(isset($audited[$l]))$incoming[$l]=($incoming[$l]??0)+1;}
        $duplicates=[];foreach($title_groups as $k=>$v)if(count($v)>1)$duplicates[]=['title'=>$k,'urls'=>$v];$dupdesc=[];foreach($desc_groups as $k=>$v)if(count($v)>1)$dupdesc[]=['description'=>$k,'urls'=>$v];
        $orphan=[];foreach($pages as $i=>$p)if($i>0&&$p['status']===200&&empty($incoming[$p['url']]))$orphan[]=['url'=>$p['url'],'title'=>$p['title'],'reason'=>'no incoming internal links within audited pages'];
        $media=[];foreach($pages as $p)foreach($p['images'] as $im)if($im['issue']||$im['filename_issue'])$media[]=['page'=>$p['url'],'page_title'=>$p['title'],'image'=>$im,'recommended_alt'=>$im['alt']?:$p['title'],'recommended_filename'=>sanitize_title($im['alt']?:$p['title']).'.jpg'];
        $index=['checks'=>[],'findings'=>[]]; foreach(['/robots.txt','/sitemap.xml','/wp-sitemap.xml','/sitemap_index.xml'] as $path){$r=self::request(self::base_url().$path);$index['checks'][$path]=['status'=>$r['status'],'final_url'=>$r['final_url'],'x_robots_tag'=>$r['x_robots_tag']??null];}
        $robots=$index['checks']['/robots.txt'];if($robots['status']!==200)$index['findings'][]=['severity'=>'warning','check'=>'robots.txt','message'=>'robots.txt was not returned with HTTP 200.'];
        $sok=false;foreach(['/sitemap.xml','/wp-sitemap.xml','/sitemap_index.xml'] as $p)if($index['checks'][$p]['status']===200)$sok=true;if(!$sok)$index['findings'][]=['severity'=>'high','check'=>'sitemap','message'=>'No checked sitemap endpoint returned HTTP 200.'];
        $variants=[];foreach(array_unique([self::base_url(),preg_replace('#^https?://#','https://www.',self::base_url())]) as $v){$r=self::request($v.'/');$variants[]=['url'=>$v.'/','status'=>$r['status'],'final_url'=>$r['final_url']];}$index['host_variants']=$variants;
        $counts=[];foreach($pages as $p)foreach($p['issues'] as $i)$counts[$i]=($counts[$i]??0)+1;$counts['duplicate-titles']=count($duplicates);$counts['duplicate-meta-descriptions']=count($dupdesc);$counts['orphan-candidates']=count($orphan);$counts['media-recommendations']=count($media);$counts['indexing-readiness-findings']=count($index['findings']);
        $total=max(1,array_sum($counts));$critical=($counts['noindex']??0)+($counts['missing-canonical']??0)+($counts['missing-title']??0);$score=max(0,min(100,100-(int)round(($total+$critical*2)*100/max(1,count($pages)*6))));
        $report=['tool_version'=>self::VERSION,'site'=>self::base_url(),'generated_at'=>current_time('mysql'),'read_only'=>true,'score'=>$score,'pages_audited'=>count($pages),'issue_counts'=>$counts,'intelligence'=>['duplicate_titles'=>$duplicates,'duplicate_meta_descriptions'=>$dupdesc,'orphan_candidates'=>$orphan],'media_recommendations'=>$media,'indexing_readiness'=>$index,'pages'=>$pages]; update_option(self::OPTION,$report,false); return $report;
    }

    private static function report(){return get_option(self::OPTION,[]);}
    public static function run_audit_action(){if(!current_user_can('manage_options'))wp_die('Unauthorized');check_admin_referer('df_run_audit');self::run_audit(isset($_POST['limit'])?(int)$_POST['limit']:50);wp_safe_redirect(admin_url('admin.php?page='.self::MENU.'&audit=done'));exit;}

    public static function dashboard(){if(!current_user_can('manage_options'))return;$r=self::report();echo '<div class="wrap"><h1>Daily Flare SEO Toolkit</h1><p>Native, read-only SEO command center. It never publishes, deletes, renames, or changes content.</p>';
        echo '<form method="post" action="'.esc_url(admin_url('admin-post.php')).'" style="margin:18px 0">';wp_nonce_field('df_run_audit');echo '<input type="hidden" name="action" value="df_run_audit"><label>Pages: <input type="number" name="limit" value="50" min="1" max="200" style="width:80px"></label> <button class="button button-primary">Run Full SEO Audit</button></form>';
        if(!$r){echo '<div class="notice notice-info"><p>No report yet. Run the audit above.</p></div></div>';return;}
        $c=$r['issue_counts']??[];echo '<div style="display:flex;gap:12px;flex-wrap:wrap">';self::card('SEO Score',($r['score']??0).'%');self::card('Pages',$r['pages_audited']??0);self::card('Problems',array_sum($c));self::card('Images',$c['media-recommendations']??0);echo '</div>';
        echo '<h2>Latest report</h2><p><strong>Generated:</strong> '.esc_html($r['generated_at']).' &nbsp; <strong>Mode:</strong> Read-only</p><table class="widefat striped"><thead><tr><th>Finding</th><th>Count</th></tr></thead><tbody>';foreach($c as $k=>$v)echo '<tr><td>'.esc_html(ucwords(str_replace('-',' ',$k))).'</td><td>'.(int)$v.'</td></tr>';echo '</tbody></table>';
        echo '<h2>Indexing readiness</h2><pre style="background:#fff;padding:15px;overflow:auto">'.esc_html(wp_json_encode($r['indexing_readiness'],JSON_PRETTY_PRINT|JSON_UNESCAPED_SLASHES)).'</pre></div>'; }
    private static function card($label,$value){echo '<div style="background:#fff;border:1px solid #ccd0d4;padding:18px;min-width:150px"><div style="font-size:13px;color:#646970">'.esc_html($label).'</div><strong style="font-size:28px">'.esc_html($value).'</strong></div>';}

    public static function findings_page(){if(!current_user_can('manage_options'))return;$r=self::report();echo '<div class="wrap"><h1>Daily Flare SEO Findings</h1>';if(!$r){echo '<p>Run an audit first.</p></div>';return;}foreach(['duplicate_titles'=>'Duplicate titles','duplicate_meta_descriptions'=>'Duplicate meta descriptions','orphan_candidates'=>'Orphan candidates','media_recommendations'=>'Media recommendations'] as $key=>$label){echo '<h2>'.esc_html($label).' ('.count($r['intelligence'][$key]??$r[$key]??[]).')</h2><pre style="background:#fff;padding:15px;max-height:360px;overflow:auto">'.esc_html(wp_json_encode($r['intelligence'][$key]??$r[$key]??[],JSON_PRETTY_PRINT|JSON_UNESCAPED_SLASHES)).'</pre>'; }echo '<h2>Page-level report</h2><pre style="background:#fff;padding:15px;max-height:600px;overflow:auto">'.esc_html(wp_json_encode($r['pages'],JSON_PRETTY_PRINT|JSON_UNESCAPED_SLASHES)).'</pre></div>';}
    public static function settings_page(){if(!current_user_can('manage_options'))return;echo '<div class="wrap"><h1>Daily Flare SEO Toolkit</h1><h2>Safety</h2><p><strong>Read-only mode is permanent in v1.0.</strong> The toolkit audits public pages and reports recommendations. It does not modify posts, media, URLs, Search Console, Bing or Yandex.</p><p><strong>Site:</strong> '.esc_html(self::base_url()).'</p><p><strong>REST report:</strong> <code>/wp-json/daily-flare/v1/seo/report</code></p><p><strong>REST audit:</strong> <code>POST /wp-json/daily-flare/v1/seo/audit</code> (administrator only)</p></div>';}

    public static function rest_routes(){register_rest_route('daily-flare/v1','/seo/report',['methods'=>'GET','permission_callback'=>function(){return current_user_can('manage_options');},'callback'=>function(){return rest_ensure_response(self::report());}]);register_rest_route('daily-flare/v1','/seo/audit',['methods'=>'POST','permission_callback'=>function(){return current_user_can('manage_options');},'callback'=>function($req){return rest_ensure_response(self::run_audit((int)($req->get_param('limit')?:50)));}]);}

    public static function register_nibwp_abilities(){if(!function_exists('wp_register_ability'))return; $defs=[
        ['dailyflare__seo-get-report','Get the latest Daily Flare SEO audit report.','readonly'],
        ['dailyflare__seo-run-audit','Run a read-only Daily Flare SEO audit and return the report.','write'],
    ]; foreach($defs as $d){try{wp_register_ability($d[0],['label'=>$d[1],'description'=>$d[1],'input_schema'=>['type'=>'object','properties'=>['limit'=>['type'=>'integer','minimum'=>1,'maximum'=>200]],'additionalProperties'=>false],'output_schema'=>['type'=>'object'],'execute_callback'=>$d[2]==='readonly'?function(){return self::report();}:function($input){return self::run_audit(isset($input['limit'])?(int)$input['limit']:50);},'permission_callback'=>function(){return current_user_can('manage_options');}]);}catch(Throwable $e){}}
    }
}
Daily_Flare_SEO_Toolkit::init();
